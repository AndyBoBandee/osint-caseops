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
- `worker`: not a separate service yet. The current fraud monitor scheduler runs inside the API process.
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
- `make smoke` starts Docker Compose, verifies API health, SQLite health, the Fraud Monitor dashboard, and the schedule API, then shuts Compose down.

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

## Fraud Monitor Providers

The current app surface is the Fraud Monitor dashboard. It uses passive HTTP GET requests to public
search providers for the fixed keyword `fraud`. Default providers are the no-key options:

- `gdelt` for the GDELT document API.
- `google_news_rss` for Google News RSS search.
- `hn_algolia` for Hacker News Algolia search.

Configure the dashboard provider list with:

```sh
OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS=gdelt,google_news_rss,hn_algolia
```

Keep the real Brave key in your local shell, password manager, or uncommitted environment file. The
API reads `BRAVE_SEARCH_API_KEY` from the process environment, and Docker Compose passes the variable
through when it is set. Do not commit the key. A saved Brave key is used only when the user requests
a detailed search from the dashboard or API.

Use `OSINT_CASEOPS_NEWS_MAX_RESULTS` to cap results per provider. Use
`OSINT_CASEOPS_FRAUD_MONITOR_SCHEDULER_SECONDS` to tune how often the API checks for due scheduled
runs. Tests and smoke checks mock or avoid live provider calls and do not require network access or
API credentials.

Provider behavior is deliberately passive and bounded:

| Provider | External request | Configuration | Per-run request limit | Timeout | Safety limit |
| --- | --- | --- | --- | --- | --- |
| `gdelt` | `GET https://api.gdeltproject.org/api/v2/doc/doc` | No key | Up to `min(OSINT_CASEOPS_NEWS_MAX_RESULTS, 50)` results for the fixed keyword | 8 seconds | Public document API only; no scraping, login, or private data access. |
| `google_news_rss` | `GET https://news.google.com/rss/search` | No key | Up to `min(OSINT_CASEOPS_NEWS_MAX_RESULTS, 50)` RSS items for the fixed keyword | 8 seconds | Public RSS search only; snippets and links are leads for analyst review. |
| `hn_algolia` | `GET https://hn.algolia.com/api/v1/search` | No key | Up to `min(OSINT_CASEOPS_NEWS_MAX_RESULTS, 50)` story hits for the fixed keyword | 8 seconds | Public Hacker News search only; comments or stories are not automated claims. |
| `brave` | `GET https://api.search.brave.com/res/v1/news/search` | `BRAVE_SEARCH_API_KEY` required | Up to `min(OSINT_CASEOPS_NEWS_MAX_RESULTS, 20)` news results for the fixed keyword | 8 seconds | Optional provider; API key must stay local and out of commits. |
| `fixture` | None | `OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER=1` required | Up to 2 deterministic local records | Not networked | Test-only public-source-style data for smoke and fixture coverage. |

The Fraud Monitor uses provider-specific query text before each request. Standard scans use the
configured no-key providers. Detailed searches use Brave only when requested and receive a
report-oriented query for the fixed keyword: `fraud (report OR warning OR investigation OR charged OR lawsuit OR enforcement)`.
Before storing results, the API deterministically filters obvious static assets and non-news records
such as JavaScript, CSS, image/font/document files, `/static/` or `/assets/` paths, CDN-style asset
URLs, and empty title/snippet records that do not look like article or report URLs. Filtering is local
and does not fetch or scrape result pages.

Provider health uses explicit states in the dashboard:

- `ready`: configured and available for passive public search.
- `missing_config`: the provider is known but required local configuration is absent.
- `unsupported`: the provider is disabled for the current environment or not recognized.
- `timeout`: the most recent provider run did not contribute results because it timed out or failed.
- `partial_success`: the most recent provider run contributed some results and also recorded an issue.

Provider configuration validation is available at `GET /fraud-monitor/configuration/validation` and in
the dashboard Providers panel. It reports whether at least one provider is ready, whether configured
providers are unsupported or missing configuration, and whether fixture mode is enabled for test-only
runs.

Scheduled scans run one job at a time. If a scheduled provider run times out or fails, the dashboard
records the provider-specific reason and the next scheduled run uses bounded backoff before retrying.
Manual runs still report the issue immediately and preserve the configured schedule interval.

For deterministic local smoke checks, use the test-only fixture provider:

```sh
OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER=1
OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS=fixture
```

The `fixture` provider is unsupported unless explicitly enabled. It returns local deterministic
public-source-style records and never makes external requests.

Fraud Monitor runs one job at a time. Manual overlap returns `409 Conflict`; scheduled overlap is
skipped and retried on the next scheduler tick without advancing `next_run_at`.

## Provider Behavior And Safety Limits

- Provider calls must stay passive HTTP GET requests.
- Default local development must not require paid API keys.
- New providers must document external requests, rate limits, and responsible-use constraints before implementation.
- Provider failures should be displayed as concise actionable messages with provider attribution.
- Public results are leads for analyst review, not automated fraud verdicts.

## Local Exports

Fraud Monitor can export reviewed local data without cloud sync:

- `GET /fraud-monitor/exports/markdown` returns a Markdown report for reviewed results.
- `GET /fraud-monitor/exports/json` returns a JSON audit bundle for backup and local review.

Both formats include:

- Generated timestamp, scope, passive methodology, provider configuration, and local-only metadata.
- Reviewed fraud monitor results only; pending results remain in the dashboard queue but are not exported.
- Evidence table rows with source URL, provider, review status, analyst note, retrieval timestamp, publication timestamp, and title.
- Trend groups with confidence-aware wording and analyst-review language.
- Responsible-use limitations that warn against unsupported allegations and remind the user to redact before sharing.

Exports are generated from the local SQLite database and returned to the user. The app does not upload
or synchronize export content.

## First Setup Tasks

1. Keep `apps/web` and `apps/api` runnable from their own directories.
2. Use `infra/docker/docker-compose.yml` for local stack orchestration.
3. Add shared schemas under `packages/shared-schemas` only when web/API contracts need them.
4. Add database migrations or schema initialization before case CRUD.
5. Keep API smoke tests in `tests/api`.
6. Add browser smoke tests under `tests/e2e` when the first case workflow exists.
