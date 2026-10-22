"""Private synthetic letters: account/session isolation, no real recipient or prose."""
import json

import pytest
from fastapi.testclient import TestClient

from app.db import get_db, init_schema
from app.security import LEGACY_SESSION_COOKIE, SESSION_COOKIE, token_hash
from test_cloud_database import pg_api

HEADERS = {"X-Sense-And-Stars": "1"}
TEXT = {"title": "TEST · Ein persönlicher Gruß", "salutation": "TEST Person,",
        "paragraphs": ["Synthetischer privater Brieftext.", "<script>test-only</script>"],
        "closing": "TEST Gruß", "sender": "TEST Absender"}


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("SENSE_AND_STARS_HOSTED", "0")
    monkeypatch.setenv("SENSE_AND_STARS_DB", str(tmp_path / "dedication.sqlite3"))
    monkeypatch.setenv("SENSE_AND_STARS_DEMO", "1")
    from app.main import app
    with TestClient(app) as client:
        yield client


def login(client, account):
    result = client.post("/api/auth/login", json=account, headers=HEADERS)
    assert result.status_code == 200, result.text
    return result.json()


def accounts(client):
    data = client.get("/api/demo").json()["accounts"]
    return {a["role"]: {k:a[k] for k in ("email", "password")} for a in data}


def seed(user_id):
    with get_db() as conn:
        return conn.execute("""INSERT INTO personal_dedications
          (user_id,title,salutation,paragraphs_json,closing,sender,content_version,created_at)
          VALUES(?,?,?,?,?,?,1,?) RETURNING id""",
          (user_id,TEXT["title"],TEXT["salutation"],json.dumps(TEXT["paragraphs"]),
           TEXT["closing"],TEXT["sender"],"2026-10-21T00:00:00+00:00")).fetchone()["id"]


def dismiss(client, identifier, version=1, **headers):
    return client.post("/api/dedication/dismiss", json={"id":identifier,"version":version},
                       headers={**HEADERS,**headers})


def test_anonymous_cannot_read_private_message(api):
    assert api.get("/api/dedication").status_code == 401
    assert dismiss(api, 1).status_code == 401
    assert presented(api, 1).status_code == 401


def test_no_default_letter_and_read_has_no_side_effects(api):
    login(api, accounts(api)["practitioner"])
    for _ in range(2):
        response = api.get("/api/dedication")
        assert response.status_code == 200 and response.json()=={"dedication":None,"auto_open":False}
        assert response.headers["cache-control"] == "no-store"
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM personal_dedications").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM personal_dedication_views").fetchone()[0] == 0
        assert conn.execute("SELECT COUNT(*) FROM personal_dedication_receipts").fetchone()[0] == 0


def exercise_private_message(client, target, other):
    user = login(client, target); identifier=seed(user["id"])
    response=client.get("/api/dedication")
    expected={"id":identifier,"version":1,**TEXT}
    assert response.json()=={"dedication":expected,"auto_open":True}
    assert response.headers["cache-control"]=="no-store"
    assert "user_id" not in response.text and "created_at" not in response.text
    assert dismiss(client,identifier,Origin="https://other.example.org").status_code==403
    assert client.get("/api/dedication").json()["auto_open"] is True
    assert dismiss(client,identifier+100).status_code==404
    assert dismiss(client,identifier,version=2).status_code==404
    assert dismiss(client,identifier).json()=={"ok":True}
    assert dismiss(client,identifier).status_code==200
    # Reload/reopening retains the complete message but no automatic repeat.
    assert client.get("/api/dedication").json()=={"dedication":expected,"auto_open":False}
    old_cookie=client.cookies.get(SESSION_COOKIE)
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM personal_dedication_views").fetchone()[0]==1
        # An unrelated editable profile name/email cannot move the target.
        conn.execute("UPDATE users SET name=? WHERE id=?",("TEST changed display",user["id"]))
    assert client.get("/api/dedication").json()["dedication"]==expected
    # A fresh session retains the account acknowledgement without an automatic repeat.
    login(client,target)
    assert client.get("/api/dedication").json()["auto_open"] is False
    assert dismiss(client,identifier).status_code==200
    # Another account cannot read or dismiss the target by guessing its ID.
    login(client,other)
    assert client.get("/api/dedication").json()=={"dedication":None,"auto_open":False}
    assert dismiss(client,identifier).status_code==404
    assert client.get("/api/dedication/"+str(identifier)).status_code==404
    # Revoked sessions do not retain a private letter or an acknowledgement.
    client.cookies.clear();client.cookies.set(SESSION_COOKIE,old_cookie)
    with get_db() as conn:
        conn.execute("DELETE FROM sessions WHERE token_hash=?",(token_hash(old_cookie),))
        assert conn.execute("SELECT COUNT(*) FROM personal_dedication_views WHERE session_token_hash=?",(token_hash(old_cookie),)).fetchone()[0]==0
    assert client.get("/api/dedication").status_code==401
    assert dismiss(client,identifier).status_code==401


def test_private_letter_isolation_and_session_lifecycle_sqlite(api):
    identities=accounts(api)
    exercise_private_message(api,identities["practitioner"],identities["admin"])


def test_private_letter_isolation_and_session_lifecycle_postgres(pg_api):
    exercise_private_message(pg_api,
       {"email":"pg-practice@example.org","password":"Test-Postgres-Passphrase"},
       {"email":"pg-admin@example.org","password":"Test-Postgres-Passphrase"})


def test_new_content_version_reappears_and_migration_preserves_letter(api):
    user=login(api,accounts(api)["practitioner"]);identifier=seed(user["id"])
    assert dismiss(api,identifier).status_code==200
    with get_db() as conn:
        conn.execute("UPDATE personal_dedications SET content_version=2 WHERE id=?",(identifier,))
    with get_db() as conn:init_schema(conn)
    with get_db() as conn:init_schema(conn)
    value=api.get("/api/dedication").json()
    assert value["auto_open"] is True and value["dedication"]["version"]==2
    assert value["dedication"]["paragraphs"]==TEXT["paragraphs"]


def test_client_account_and_forged_payload_cannot_access_other_letter(api):
    identities=accounts(api);user=login(api,identities["practitioner"]);identifier=seed(user["id"])
    login(api,identities["client"])
    assert api.get("/api/dedication").json()=={"dedication":None,"auto_open":False}
    assert dismiss(api,identifier).status_code==404
    response=api.post("/api/dedication/dismiss",json={"id":identifier,"version":1,"user_id":user["id"]},headers=HEADERS)
    assert response.status_code==422


def test_expired_session_does_not_access_private_letter(api):
    user=login(api,accounts(api)["practitioner"]);identifier=seed(user["id"])
    with get_db() as conn:conn.execute("UPDATE sessions SET expires_at='2000-01-01' WHERE user_id=?",(user["id"],))
    assert api.get("/api/dedication").status_code==401
    assert dismiss(api,identifier).status_code==401


def test_legacy_session_cookie_can_acknowledge_own_letter(api):
    user=login(api,accounts(api)["practitioner"]);identifier=seed(user["id"]);cookie=api.cookies.get(SESSION_COOKIE)
    api.cookies.clear();api.cookies.set(LEGACY_SESSION_COOKIE,cookie)
    assert api.get("/api/dedication").json()["auto_open"] is True
    assert dismiss(api,identifier).status_code==200
    assert api.get("/api/dedication").json()["auto_open"] is False


def test_corrupt_private_content_fails_closed(api):
    user=login(api,accounts(api)["practitioner"]);identifier=seed(user["id"])
    with get_db() as conn:conn.execute("UPDATE personal_dedications SET paragraphs_json=? WHERE id=?",('{invalid',identifier))
    response=api.get("/api/dedication")
    assert response.status_code==503 and TEXT["salutation"] not in response.text



def presented(client, identifier, version=1, **headers):
    return client.post("/api/dedication/presented", json={"id":identifier,"version":version},
                       headers={**HEADERS,**headers})


def exercise_first_presentation(client, target, other):
    user=login(client,target);identifier=seed(user["id"])
    expected={"id":identifier,"version":1,**TEXT}
    # Merely fetching is not presentation and must not write a durable receipt.
    for _ in range(2):
        assert client.get("/api/dedication").json()=={"dedication":expected,"auto_open":True}
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM personal_dedication_receipts").fetchone()[0]==0
    assert presented(client,identifier,Origin="https://other.example.org").status_code==403
    assert presented(client,identifier+100).status_code==404
    assert presented(client,identifier,version=2).status_code==404
    acknowledgement=presented(client,identifier)
    assert acknowledgement.json()=={"ok":True}
    assert acknowledgement.headers["cache-control"]=="no-store"
    with get_db() as conn:
        receipt=dict(conn.execute("SELECT * FROM personal_dedication_receipts").fetchone())
        assert receipt["user_id"]==user["id"] and receipt["dedication_id"]==identifier
        assert conn.execute("SELECT COUNT(*) FROM personal_dedication_views").fetchone()[0]==0
    assert presented(client,identifier).status_code==200
    with get_db() as conn:
        assert dict(conn.execute("SELECT * FROM personal_dedication_receipts").fetchone())==receipt
    assert client.get("/api/dedication").json()=={"dedication":expected,"auto_open":False}
    # Another login, session revocation, and routine schema startup cannot erase it.
    assert client.post("/api/auth/logout",json={},headers=HEADERS).status_code==200
    login(client,target)
    with get_db() as conn:init_schema(conn)
    with get_db() as conn:init_schema(conn)
    assert client.get("/api/dedication").json()=={"dedication":expected,"auto_open":False}
    assert dismiss(client,identifier).status_code==200
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM personal_dedication_receipts").fetchone()[0]==1
    # The settings read remains available; another account can neither read nor mark it.
    login(client,other)
    assert client.get("/api/dedication").json()=={"dedication":None,"auto_open":False}
    assert presented(client,identifier).status_code==404
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM personal_dedication_receipts").fetchone()[0]==1
    login(client,target)
    with get_db() as conn:
        conn.execute("UPDATE personal_dedications SET content_version=2 WHERE id=?",(identifier,))
    assert client.get("/api/dedication").json()=={"dedication":{**expected,"version":2},"auto_open":True}
    assert presented(client,identifier).status_code==404
    assert presented(client,identifier,version=2).status_code==200
    assert client.get("/api/dedication").json()["auto_open"] is False
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM personal_dedication_receipts").fetchone()[0]==2


def test_first_presentation_survives_logins_sqlite(api):
    identities=accounts(api)
    exercise_first_presentation(api,identities["practitioner"],identities["admin"])


def test_first_presentation_survives_logins_postgres(pg_api):
    exercise_first_presentation(pg_api,
       {"email":"pg-practice@example.org","password":"Test-Postgres-Passphrase"},
       {"email":"pg-admin@example.org","password":"Test-Postgres-Passphrase"})


def test_presentation_checks_active_session_and_payload(api):
    identity=accounts(api)["practitioner"];user=login(api,identity);identifier=seed(user["id"])
    for payload in [{"id":identifier,"version":1,"user_id":user["id"]},
                    {"id":identifier,"version":True},{"id":identifier,"version":"1"},
                    {"id":identifier,"version":0}]:
        response=api.post("/api/dedication/presented",json=payload,headers=HEADERS)
        assert response.status_code==422
    with get_db() as conn:
        conn.execute("UPDATE sessions SET expires_at='2000-01-01' WHERE user_id=?",(user["id"],))
    assert presented(api,identifier).status_code==401
    with get_db() as conn:
        assert conn.execute("SELECT COUNT(*) FROM personal_dedication_receipts").fetchone()[0]==0


def exercise_legacy_migration(client,target,other):
    user=login(client,target);identifier=seed(user["id"])
    own_session=token_hash(client.cookies.get(SESSION_COOKIE))
    login(client,other);foreign_session=token_hash(client.cookies.get(SESSION_COOKIE))
    stamp="2026-10-21T01:02:03+00:00"
    with get_db() as conn:
        conn.execute("INSERT INTO personal_dedication_views VALUES(?,?,?,?)",(identifier,own_session,1,stamp))
        # Even corrupt legacy data from a different owner's session cannot count as presentation.
        conn.execute("INSERT INTO personal_dedication_views VALUES(?,?,?,?)",(identifier,foreign_session,2,stamp))
        before_letter=dict(conn.execute("SELECT * FROM personal_dedications WHERE id=?",(identifier,)).fetchone())
        before_views=[dict(row) for row in conn.execute("SELECT * FROM personal_dedication_views ORDER BY content_version")]
    with get_db() as conn:init_schema(conn)
    with get_db() as conn:init_schema(conn)
    with get_db() as conn:
        assert dict(conn.execute("SELECT * FROM personal_dedications WHERE id=?",(identifier,)).fetchone())==before_letter
        assert [dict(row) for row in conn.execute("SELECT * FROM personal_dedication_views ORDER BY content_version")]==before_views
        rows=[dict(row) for row in conn.execute("SELECT * FROM personal_dedication_receipts")]
        assert len(rows)==1 and rows[0]["content_version"]==1
        assert rows[0]["user_id"]==user["id"] and rows[0]["presented_at"]==stamp
    login(client,target)
    assert client.get("/api/dedication").json()["auto_open"] is False
    with get_db() as conn:
        conn.execute("DELETE FROM personal_dedications WHERE id=?",(identifier,))
        assert conn.execute("SELECT COUNT(*) FROM personal_dedication_receipts").fetchone()[0]==0



def test_migration_only_backfills_owned_acknowledgements_and_preserves_records_sqlite(api):
    identities=accounts(api)
    exercise_legacy_migration(api,identities["practitioner"],identities["admin"])


def test_migration_only_backfills_owned_acknowledgements_and_preserves_records_postgres(pg_api):
    exercise_legacy_migration(pg_api,
       {"email":"pg-practice@example.org","password":"Test-Postgres-Passphrase"},
       {"email":"pg-admin@example.org","password":"Test-Postgres-Passphrase"})


def test_each_account_has_its_own_first_presentation(api):
    identities=accounts(api)
    user=login(api,identities["practitioner"]);first=seed(user["id"])
    assert presented(api,first).status_code==200
    other=login(api,identities["admin"]);second=seed(other["id"])
    assert api.get("/api/dedication").json()["auto_open"] is True
    assert presented(api,first).status_code==404
    assert presented(api,second).status_code==200
    with get_db() as conn:
        pairs={(row["user_id"],row["dedication_id"]) for row in conn.execute("SELECT * FROM personal_dedication_receipts")}
        assert pairs=={(user["id"],first),(other["id"],second)}
    login(api,identities["practitioner"])
    assert api.get("/api/dedication").json()["dedication"]["id"]==first
    assert api.get("/api/dedication").json()["auto_open"] is False
