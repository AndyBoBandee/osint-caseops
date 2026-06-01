# Milestones

This file tracks the current Fraud Monitor direction. The earlier OSINT CaseOps
case, entity, enrichment, finding, graph, timeline, and report roadmap is legacy
direction unless it is explicitly reintroduced.

## Milestone 1: Local Foundation

Status: Complete.

Deliverables:

- Monorepo structure.
- Next.js web app shell.
- FastAPI backend shell.
- SQLite database setup.
- Docker Compose for local development.
- Health checks.
- Responsible-use and brand guidance.

Acceptance:

- Developer can start the local stack.
- Web app can call API health endpoints.
- API can read and write to SQLite.
- Local runtime data stays outside commits.

Verification:

- `infra/docker/docker-compose.yml` starts the `api` and `web` services.
- The web app reads `API_BASE_URL` and renders API health.
- The API initializes the local SQLite database on startup and `/health/db`
  writes and reads the `app_health` row.
- `tests/api/test_health.py` verifies API health and SQLite read/write behavior
  against an isolated temporary data directory.

## Milestone 2: Fraud Monitor Dashboard

Status: Complete.

Deliverables:

- Fraud Monitor dashboard as the first product surface.
- Fixed keyword workflow for `fraud`.
- Provider readiness panel.
- Manual run control.
- Local schedule control.
- Runtime status for idle, running, ready provider count, and latest provider
  issue.
- Job history and dashboard metrics.

Acceptance:

- User can open the app and immediately see the Fraud Monitor dashboard.
- User can tell whether the API and configured providers are usable.
- User can run one scan at a time or enable scheduled local scans.
- Overlapping manual or scheduled jobs do not corrupt state.

Verification:

- `tests/api/test_fraud_monitor.py` verifies dashboard bootstrap, provider
  readiness, manual job execution, partial provider failures, overlap rejection,
  and scheduled run behavior.
- `scripts/smoke.sh` verifies dashboard rendering, schedule updates, and manual
  run behavior through the Docker stack.

## Milestone 3: Public Result Ingestion And Review

Status: Complete.

Deliverables:

- Public provider integrations for passive result ingestion.
- Provider run records with status, error text, and result counts.
- Stored public results with source URL, publisher, title, snippet, published
  date when available, retrieval timestamp, provider, and query keyword.
- Analyst review statuses: pending, relevant, and not relevant.
- Review filters by status, provider, and evidence state.
- Basic trend grouping by keyword, source, time window, and repeated theme.

Acceptance:

- User can run a scoped fraud scan across configured ready providers.
- Returned public results are stored for analyst review.
- Provider failures are visible without blocking successful provider results.
- Trend language remains confidence-aware and requires analyst review.

Verification:

- `tests/api/test_fraud_monitor.py` verifies provider-backed job results,
  normalized provider failures, review status updates, and dashboard result
  fields.
- `tests/api/test_news_monitoring.py` verifies the reusable public news
  ingestion, review, evidence, trend grouping, provider failure, and persistence
  behavior.

## Milestone 4: Evidence Links And Deterministic Smoke

Status: Complete.

Deliverables:

- Save public result source links as evidence.
- Analyst note capture when saving evidence.
- Evidence count and saved state on the dashboard.
- Test-only fixture provider gated by `OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER`.
- Docker smoke flow that makes no live provider requests.

Acceptance:

- User can mark a result relevant and save its source as evidence.
- Evidence saves retain the source URL, query keyword, and analyst note.
- Fixture smoke runs are deterministic and cannot be enabled accidentally by
  naming the provider alone.
- The product can be validated without network-backed provider calls.

Verification:

- `tests/api/test_fraud_monitor.py` verifies evidence wrapper behavior and
  fixture provider gating.
- `scripts/smoke.sh` verifies fixture run, review update, evidence save,
  filters, and schedule behavior through the Docker stack.
- `make smoke` is the required end-to-end gate for this milestone.

## Milestone 5: Review Operations

Status: Complete.

Deliverables:

- Result search and sort controls.
- Clear duplicate or already-saved indicators.
- Editable analyst notes after evidence save.
- Bulk review actions for stored results.
- Pagination or virtualized rendering for larger result sets.
- Source-open affordances that keep local state intact.

Acceptance:

- User can work a larger fraud result queue without losing context.
- User can correct review and evidence notes after initial save.
- User can identify already-handled or duplicate sources quickly.
- Bulk actions require clear user intent and never make automated fraud
  conclusions.

Verification:

- Backend tests cover note edits, bulk review updates, duplicate handling, and
  pagination boundaries.
- Frontend tests or rendered QA cover filters, search, bulk actions, and note
  edit flows.
- `make test-fast`, web build, and `make smoke` pass.

## Milestone 6: Provider Quality And Trend Utility

Status: Complete.

Deliverables:

- Provider-specific request limits and timeout documentation.
- Provider health details that distinguish unsupported, missing configuration,
  timeout, partial success, and ready states.
- Trend groups that are useful for triage rather than claims.
- Source-quality and recency cues for analyst prioritization.
- Safer retry/backoff behavior for scheduled runs.

Acceptance:

- User can understand why a provider did or did not contribute results.
- Scheduled scans behave predictably when a provider is slow or unavailable.
- Trend summaries help prioritize review while preserving analyst judgment.
- All provider behavior remains passive and public-source only.

Verification:

- API tests cover provider status classification, timeout handling, retry/backoff
  decisions, and trend grouping edge cases.
- Docs name external request behavior, rate limits, configuration, and safety
  limits for each provider.
- Rendered QA verifies provider health details, trend triage cues, and
  source-quality/recency cues on the dashboard.
- `make check` and `make smoke` pass with fixture-provider coverage.

## Milestone 7: Local Export And Audit Bundle

Status: Complete.

Deliverables:

- Markdown export for reviewed fraud monitor results.
- JSON bundle export for local audit and backup.
- Evidence table with source URLs, provider, review status, analyst notes, and
  retrieval timestamps.
- Trend summary section with confidence-aware wording.
- Export metadata for scope, methodology, provider configuration, and generated
  timestamp.

Acceptance:

- User can export reviewed local data without cloud sync.
- Exports include enough provenance to audit where each result came from.
- Exports avoid unsupported allegations and preserve responsible-use language.

Verification:

- API tests cover export structure, escaping, local-only data access, and empty
  state behavior.
- Smoke verifies the user-visible export controls and both export endpoints with
  deterministic fixture-provider coverage.

## Milestone 8: Pilot Readiness

Status: Complete.

Deliverables:

- Setup checklist for local operators.
- Configuration validation for provider choices and fixture-only test mode.
- Data retention and cleanup guidance.
- Release checklist with privacy, safety, and local-storage review.
- Stable product docs that route new work through Fraud Monitor.

Acceptance:

- A new local operator can bootstrap, run, review, save evidence, and export
  without undocumented steps.
- Test-only provider behavior is clearly separated from real provider behavior.
- Current docs no longer steer default work toward the legacy OSINT CaseOps
  path.

Verification:

- `make bootstrap`, `make check`, and `make smoke` pass from a clean checkout.
- Rendered QA validates the primary dashboard workflow with fixture-provider
  configuration, review, evidence, and export controls.
- Documentation review confirms the legacy path is labeled as legacy and current
  next work follows the Fraud Monitor milestones.
