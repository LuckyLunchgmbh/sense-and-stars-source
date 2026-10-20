"""Persisted personal settings and immutable agreed appointment prices."""
import pytest

from test_crm import api, future_slot, login, post
from test_cloud_database import pg_api


def patch(api, payload):
    return api.patch('/api/auth/me', json=payload, headers={'X-Sense-And-Stars': '1'})


def book(api, client_id, *, day=40, minutes=60, **kwargs):
    return post(api, '/api/appointments', dict(client_id=client_id,
                start_at=future_slot(day), duration_minutes=minutes,
                title='Synthetische Preissitzung', **kwargs))


def test_profile_edit_persists_without_changing_other_fields_or_other_accounts(api):
    initial = login(api, 'practitioner')
    assert initial['hourly_rate_cents'] is None
    result = patch(api, {'name': ' Marina ', 'hourly_rate_cents': 8750})
    assert result.status_code == 200, result.text
    assert result.json() == {**initial, 'name': 'Marina', 'hourly_rate_cents': 8750}
    assert api.get('/api/auth/me').json() == result.json()
    assert patch(api, {'tour_completed': True}).json()['name'] == 'Marina'
    assert login(api, 'admin')['hourly_rate_cents'] is None
    assert login(api, 'practitioner')['hourly_rate_cents'] == 8750
    assert patch(api, {'hourly_rate_cents': None}).json()['hourly_rate_cents'] is None


@pytest.mark.parametrize('payload', [{}, {'name': ''}, {'name': '  '},
    {'name': None}, {'name': 'x' * 121}, {'hourly_rate_cents': True},
    {'hourly_rate_cents': 12.1}, {'hourly_rate_cents': '1200'},
    {'hourly_rate_cents': -1}, {'hourly_rate_cents': 1000001},
    {'email': 'new@example.test'}, {'role': 'admin'}, {'tour_completed': None}])
def test_profile_rejects_invalid_and_unrequested_fields(api, payload):
    login(api, 'practitioner')
    assert patch(api, payload).status_code == 422


def test_client_may_edit_name_but_cannot_set_or_clear_staff_hourly_rate(api):
    user = login(api, 'client')
    assert user.get('hourly_rate_cents') is None
    assert patch(api, {'name': 'Fiktiver Portalname'}).status_code == 200
    for rate in (0, 12000, None):
        assert patch(api, {'hourly_rate_cents': rate}).status_code == 403


def test_auto_price_rounding_explicit_free_override_and_agreed_price_snapshot(api):
    login(api, 'practitioner')
    cid = api.get('/api/clients').json()[0]['id']
    assert patch(api, {'hourly_rate_cents': 10001}).status_code == 200
    first = book(api, cid, minutes=30)
    assert first.status_code == 201, first.text
    assert first.json()['price_cents'] == 5001  # half a cent rounds up
    assert book(api, cid, day=41, minutes=90, price_cents=None).json()['price_cents'] == 15002
    assert book(api, cid, day=42, minutes=90, price_cents=0).json()['price_cents'] == 0
    assert book(api, cid, day=43, minutes=90, price_cents=12345).json()['price_cents'] == 12345
    patch(api, {'hourly_rate_cents': 8000})
    existing = next(a for a in api.get('/api/appointments').json() if a['id'] == first.json()['id'])
    assert existing['price_cents'] == 5001
    assert book(api, cid, day=44, minutes=45).json()['price_cents'] == 6000


def test_missing_rate_and_portal_and_test_appointments_have_zero_price(api):
    login(api, 'practitioner')
    cid = api.get('/api/clients').json()[0]['id']
    assert book(api, cid).json()['price_cents'] == 0
    patch(api, {'hourly_rate_cents': 10000})
    case = post(api, '/api/practice/clients/examples', {}).json()[0]
    assert book(api, case['id'], day=41, price_cents=9999).json()['price_cents'] == 0
    user = login(api, 'client')
    assert book(api, user['client_id'], day=42).json()['price_cents'] == 0
    assert book(api, user['client_id'], day=43, price_cents=None).json()['price_cents'] == 0
    assert book(api, user['client_id'], day=44, price_cents=1).status_code == 403


@pytest.mark.parametrize('value', [True, 1.5, '3000'])
def test_price_requires_integer_cents(api, value):
    login(api, 'practitioner')
    cid = api.get('/api/clients').json()[0]['id']
    assert book(api, cid, price_cents=value).status_code == 422


def test_profile_schema_migration_is_idempotent_and_preserves_user_and_prices(api):
    from app.main import initialize
    login(api, 'practitioner')
    patch(api, {'name': 'Marina', 'hourly_rate_cents': 12500})
    cid = api.get('/api/clients').json()[0]['id']
    appointment = book(api, cid).json()
    initialize()
    initialize()
    assert api.get('/api/auth/me').json()['hourly_rate_cents'] == 12500
    assert next(a for a in api.get('/api/appointments').json() if a['id'] == appointment['id'])['price_cents'] == 12500


def test_postgres_profile_and_price_snapshot_survive_reinitialization(pg_api):
    result = post(pg_api, '/api/auth/login', {
        'email': 'pg-practice@example.org', 'password': 'Test-Postgres-Passphrase'})
    assert result.status_code == 200
    assert patch(pg_api, {'name': 'Marina QA', 'hourly_rate_cents': 10001}).status_code == 200
    client = post(pg_api, '/api/clients', {'name': 'Fiktiver Preisfall', 'email': 'price-case@example.org'})
    assert client.status_code == 201, client.text
    appointment = book(pg_api, client.json()['id'], minutes=30)
    assert appointment.status_code == 201, appointment.text
    assert appointment.json()['price_cents'] == 5001
    patch(pg_api, {'hourly_rate_cents': 9000})
    from app.main import initialize
    initialize()
    assert pg_api.get('/api/auth/me').json()['hourly_rate_cents'] == 9000
    assert pg_api.get('/api/appointments').json()[0]['price_cents'] == 5001
