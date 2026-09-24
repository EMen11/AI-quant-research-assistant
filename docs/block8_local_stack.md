# Block 8 local persistent stack

## Architecture and authority boundaries

The local path is `Streamlit -> FastAPI -> application service -> explicit SQLAlchemy
repositories -> PostgreSQL`. Domain and trust models do not import Streamlit, FastAPI,
SQLAlchemy, or PostgreSQL. FastAPI validates public Pydantic contracts; the application service
owns transaction boundaries; repositories map immutable domain results to separate ORM rows.

`APP_MODE=demo` remains the public, deterministic six-view dashboard. It imports no live client,
opens no API or database connection, initializes no Anthropic client, and uses only committed local
artifacts. `APP_MODE=live` means the local transport and persistence path is active. Its current
workflow input is still explicitly labelled `frozen_offline_fixture`: it is not live market data,
not a live provider response, and makes no Anthropic or market-provider call. No Anthropic key is
required for this persisted fixture path. A key becomes relevant only for a separately authorized
and configured provider workflow.

`psycopg[binary]` is used as a reproducible local/MVP packaging compromise. It is not asserted to
be the correct universal production choice; production packaging must be selected for the target
platform, patching process, observability and security requirements.

## Start and stop

The defaults below are deliberately local placeholders, not production secrets:

```sh
BLOCK8_POSTGRES_DB=ai_quant_local \
BLOCK8_POSTGRES_USER=ai_quant_local \
BLOCK8_POSTGRES_PASSWORD=block8-local-placeholder \
docker compose up --build -d
docker compose ps
docker compose logs --no-color --tail=100
docker compose down
```

The API is exposed at `http://127.0.0.1:8000` and Streamlit at
`http://127.0.0.1:8501`. Override only the host ports with `BLOCK8_API_PORT` and
`BLOCK8_STREAMLIT_PORT`. Do not put real credentials in Compose or the repository.

PostgreSQL owns a named development volume, `ai-quant-block8-postgres-data`, on the private Compose
network. The one-shot `migrate` service is the sole migration owner. The API starts only after
PostgreSQL is healthy and migrations finish; Streamlit starts only after the API healthcheck passes.
Application containers run as the unprivileged `app` user and receive `SIGTERM` with a bounded
grace period.

## Migrations and empty-database test

Normal upgrade:

```sh
DATABASE_URL='postgresql+psycopg://USER:PLACEHOLDER@HOST:5432/DB' \
uv run --frozen alembic upgrade head
```

For the destructive empty-database proof, use the dedicated override. It fixes the database, project,
host ports and volume to disposable names containing `block8-test`:

```sh
BLOCK8_API_PORT=18000 BLOCK8_STREAMLIT_PORT=18501 \
docker compose -p ai-quant-block8-test \
  -f compose.yaml -f compose.block8-test.yaml up -d postgres migrate api
BLOCK8_API_PORT=18000 BLOCK8_STREAMLIT_PORT=18501 \
docker compose -p ai-quant-block8-test \
  -f compose.yaml -f compose.block8-test.yaml ps
docker build --target test -t ai-quant-block8-test-runner .
docker run --rm --network ai-quant-block8-test_block8-private \
  -e BLOCK8_TEST_DATABASE_URL=postgresql+psycopg://ai_quant_block8_test:block8-test-local-placeholder@postgres:5432/ai_quant_block8_test \
  ai-quant-block8-test-runner pytest -q tests/integration/test_block8_persistence_api.py
docker volume inspect ai-quant-block8-test-postgres-data --format '{{.Name}}'
```

The last command must print exactly `ai-quant-block8-test-postgres-data`. Only after visually
confirming that the resolved name contains the literal marker `block8-test`, remove this explicit
test project and its one disposable volume:

```sh
docker compose -p ai-quant-block8-test \
  -f compose.yaml -f compose.block8-test.yaml down --volumes
```

Never run `docker volume prune`; never remove `ai-quant-block8-postgres-data`, the normal development
volume. Because the override starts from a new named volume and the `migrate` one-shot service runs
before the API, this is the empty-PostgreSQL migration proof.

The default `runtime` target contains the installed application, `app.py`, Alembic configuration
and migrations, methodology documents, and versioned reports. It intentionally contains neither
the repository `tests/` directory nor pytest, Ruff, or the uv executable. Development tools exist
only in the separate `test` target shown above.

The final pre-release migration revision is `20260924_0002`. The earlier uncommitted
`20260924_0001` revision was ephemeral, local and is not supported as a predecessor in the final
migration graph. This does not claim that no external consumer could ever have stamped that old
identifier. A database carrying it must be recreated from an empty database or migrated through an
explicitly designed manual path before use; Alembic fails closed because the old identifier is not
a known current revision. No application or migration code deletes such a database automatically.

## API

- `POST /analyses`: synchronous offline-fixture workflow. The first request is `201`; the same
  `Idempotency-Key` and canonical payload returns the same row with `200`; the same key and a
  different payload returns `409`. A PostgreSQL transaction-scoped advisory lock serializes a key.
  Workflow or persistence failure rolls back the entire transaction.
- `GET /analyses/{id}` and `GET /analyses/{id}/evidence`: `404` when absent.
- `POST /analyses/{id}/reviews`: appends a review only after server-side run/draft/version checks.
  Approval additionally requires `eligible_for_review`; conflicts return `409`.
- `GET /evaluations/latest`: latest persisted evaluation or `404` when none has been recorded. The
  current committed versioned evaluation is inserted idempotently with the first analysis.
- `GET /health`: verifies that the API can execute `SELECT 1` against PostgreSQL.

Example with nonsensitive local values:

```sh
curl -i -X POST http://127.0.0.1:8000/analyses \
  -H 'Content-Type: application/json' \
  -H 'Idempotency-Key: local-example-0001' \
  -d '{"scenario":"valid","data_mode":"frozen_offline_fixture"}'
```

Public errors have a stable `{ "error": { "code", "message" } }` shape and do not include SQL,
stack traces, secrets, prompts, or raw internal exceptions. OpenAPI contains only public schemas.

## Versioning, reviews, and append-only limits

Draft versions are positive and unique per run. Claims and findings are separate historical rows.
Claim references are normalized into the ordered association tables `draft_claim_metric_refs` and
`draft_claim_evidence_refs`; composite foreign keys require the claim and referenced metric or
evidence to belong to the same run. Reference positions are positive and unique per claim, while
duplicate references are rejected. `draft_claims.declared_metric_ids` and
`draft_claims.declared_evidence_ids` are immutable JSONB string-array audit inputs, including
rejected declarations. They are never evidence of acceptance and never act as foreign keys. Only
the ordered association tables are authoritative accepted references. `GET /analyses/{id}` labels
and returns both concepts separately; a corrected version may explicitly replace its declarations,
while the previous version remains unchanged. All association foreign keys use `ON DELETE RESTRICT`: the
append-only repository does not expose deletion, so cascades would hide accidental history loss.
Reviews always append a new row and are bound to the exact run, draft, and current version; no
repository exposes update or delete methods for historical artifacts. Corrections must become a new
draft version rather than overwrite an old one. A correction locks the stable `research_runs` row
with `SELECT ... FOR UPDATE`, then rereads and compares the expected draft/version. The winner
creates one new version; stale concurrent writers receive `409`. The server reuses the existing
deterministic validators, assessment and renderer. `eligible_for_review` is never an approval: a
new explicit human review is required for the corrected version.

This is an application-level append-only guarantee backed by constraints and repository APIs. It is
not regulatory, cryptographic, WORM, or administrator-proof immutability. A database administrator
can still alter rows outside the application. Reviewer text is entered by a user and remains
explicitly unverified and unauthenticated; it is not proof of identity.
