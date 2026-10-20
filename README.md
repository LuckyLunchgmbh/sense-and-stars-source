# Sense & Stars (SoulFlow)

Sense & Stars, originally named SoulFlow, is a German-language web application for one spiritual counselling
practice. It includes client and appointment management, astronomical radix
calculations, a client portal, an open learning workspace, personal bookmarks
and notebooks, fictional practice cases, and a symbolic body view.

This repository is the complete public application source for the deployed
release. `SOURCE-MANIFEST.json` records the exported file hashes. Internal
project administration and runtime data are excluded. No production credentials
or client records are required to build the application.

## License and scope

Original SoulFlow application code is licensed under **GNU AGPL version 3**.
See `LICENSE` and `THIRD_PARTY_NOTICES.md` for the applicable notices and the
separate licenses of dependencies. The symbolic interpretation and learning
exercises are not medical diagnosis, therapy, evidence of remote perception,
or a professional qualification.

The deployed release must offer this complete corresponding source to its
network users. Configure `SOULFLOW_SOURCE_URL` to the matching public release
tag or commit, rather than an unrelated or private repository.

## Build and run locally

Requirements: Python 3.12, Node.js 24 and npm. Dependencies are installed only
inside the checkout. The local demo contains fictional data and binds only to
the loopback interface.

```sh
git clone https://github.com/LuckyLunchgmbh/sense-and-stars-source.git
cd sense-and-stars-source
python3.12 scripts/setup.py
.venv/bin/python scripts/run.py --demo --open
```

Without the demo, create private accounts using hidden password entry:

```sh
.venv/bin/python scripts/account.py create --role admin
.venv/bin/python scripts/account.py create --role practitioner
.venv/bin/python scripts/run.py
```

Runtime data is stored in the ignored `data/` directory. Never commit it.

## Verification

```sh
.venv/bin/python -m pytest -c backend/pytest.ini backend/tests -q
npm test --prefix frontend
npm run build --prefix frontend
node --check frontend/public/sw.js
```

The PostgreSQL integration tests additionally require an explicitly isolated
test database through `SOULFLOW_TEST_POSTGRES_URL`. They create and remove their
own test schemas. Never point tests at unrelated customer databases. The
repository workflow supplies a disposable PostgreSQL service for these tests.

## Hosted deployment

Vercel builds the frontend and the Python API from `vercel.json`. Deploy from
source on Linux; do not upload macOS native build artifacts as a prebuilt
function. Frontend and API share one HTTPS origin.

Required server-side environment variables are described in `.env.example`:

- `SOULFLOW_HOSTED=1`, `SOULFLOW_DEMO=0`.
- `SOULFLOW_PUBLIC_ORIGIN`: exact canonical HTTPS origin.
- `DATABASE_URL`: durable PostgreSQL connection with TLS.
- `SOULFLOW_SWISS_LICENSE=agpl-3.0` for this release.
- `SOULFLOW_SOURCE_URL`: matching publicly accessible source tag or commit.
- `CRON_SECRET`: private random value, at least 24 characters.

Enter real values through private environment configuration. Do not pass
passwords or connection strings through command-line arguments, screenshots,
repository files or application logs. The application deliberately refuses an
ephemeral SQLite fallback in hosted mode and exposes no public demo accounts.

The prepared Vercel cron checks source-update eligibility daily; a content
cycle is due after fourteen days. New source-reading lessons remain drafts.
Editing and publication are separate administrative actions. An authenticated
operator can initialize the update state with
`scripts/learning_refresh.py --hosted`; this never publishes lessons.

Before use with real client data, validate the actual deployment, account
ownership, device behaviour, backups and recovery, retention and privacy
requirements, and the editorial contents. A passing synthetic test is not
approval for real client or health data.
