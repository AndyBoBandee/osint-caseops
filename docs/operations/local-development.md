# Local Development

## Expected Stack

- Node.js for the web app.
- Python for the API.
- SQLite for local data.
- Playwright for screenshots and browser smoke tests in later milestones.
- Docker Compose for local orchestration.

## Services

- `web`: Next.js frontend.
- `api`: FastAPI backend.
- `worker`: lightweight background job process, added in a later milestone.
- SQLite runs as a local database file mounted into the app data directory, not as a separate service.

## Root Commands

Use the root `Makefile` for day-to-day work:

```sh
make bootstrap
make dev
make test-fast
make test
make check
make smoke
```

- `make bootstrap` installs API and web dependencies.
- `make dev` runs the API with reload and the web app with Next dev.
- `make test-fast` runs API tests and web lint.
- `make test` adds the Next production build.
- `make check` runs repo hygiene, tests, build, audit, and Compose config.
- `make smoke` starts Docker Compose, verifies API health, SQLite health, and the web-to-API health panel, then shuts Compose down.

Use `make api` or `make web` to run only one service. Use `make docker-up`, `make docker-down`, and `make docker-logs` for direct Compose control.

Docker Compose builds and starts the web service with `next start` so full-stack smoke checks do not rewrite development-only generated files. Use `make dev` or `make web` when you need frontend hot reload.

## Local Data Paths

Default local data should live under:

```text
data/
  cases/
  exports/
  tmp/
```

Case evidence should use this pattern:

```text
data/cases/{case_id}/
  case.json
  evidence/
    screenshots/
    html/
    files/
  reports/
  exports/
```

## Development Principles

- Keep the MVP runnable locally.
- Prefer deterministic local tests for enrichment parsers.
- Treat network-backed enrichment tests as integration tests.
- Do not require paid API keys for the default workflow.
- Make external requests visible in enrichment run logs.

## Public News Monitoring Providers

Milestone 4 public news monitoring uses passive HTTP GET requests to public search providers. The
default no-key provider is Hacker News Algolia (`OSINT_CASEOPS_NEWS_PROVIDER=hn_algolia`) so local
development and smoke checks can exercise ingestion without a paid key. Optional providers are:

- `OSINT_CASEOPS_NEWS_PROVIDER=brave` with `BRAVE_SEARCH_API_KEY` for Brave News Search.
- `OSINT_CASEOPS_NEWS_PROVIDER=google_news_rss` for Google News RSS search.
- `OSINT_CASEOPS_NEWS_PROVIDER=gdelt` for the GDELT document API.

Use `OSINT_CASEOPS_NEWS_MAX_RESULTS` to cap results per keyword. Tests mock provider responses and
do not require network access or API credentials.

## First Setup Tasks

1. Keep `apps/web` and `apps/api` runnable from their own directories.
2. Use `infra/docker/docker-compose.yml` for local stack orchestration.
3. Add shared schemas under `packages/shared-schemas` only when web/API contracts need them.
4. Add database migrations or schema initialization before case CRUD.
5. Keep API smoke tests in `tests/api`.
6. Add browser smoke tests under `tests/e2e` when the first case workflow exists.
