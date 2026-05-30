# Milestones

## Milestone 1: Repository Foundation

Status: Complete.

Deliverables:

- Project folder structure.
- Initial docs.
- Web app scaffold.
- API scaffold.
- Docker Compose.
- SQLite setup.
- Basic health checks.

Acceptance:

- Developer can start the local stack.
- Web app can call API health endpoint.
- API can read and write to SQLite.

Verification:

- `infra/docker/docker-compose.yml` starts the `api` and `web` services.
- The web app reads `API_BASE_URL` and renders the API `/health` result in the foundation status panel.
- The API initializes the local SQLite database on startup and `/health/db` writes and reads the `app_health` row.
- `tests/api/test_health.py` verifies API health and SQLite read/write behavior against an isolated temporary data directory.

## Milestone 2: Case And Entity System

Status: Complete.

Deliverables:

- Case CRUD.
- Entity CRUD.
- Scope acknowledgment.
- Tags and notes.
- Case dashboard.

Acceptance:

- User can create a scoped case.
- User can add a domain or URL entity.
- Case and entity records persist after restart.

Verification:

- The API exposes SQLite-backed CRUD endpoints for cases, nested case entities, and direct entity updates/deletes.
- Case creation requires an explicit lawful public-source scope acknowledgment and records the acknowledgment timestamp.
- Domain and URL entities are normalized and validated before persistence.
- The web app renders a case dashboard with case create/read/update/delete controls, entity create/read/update/delete controls, tags, notes, and scope status.
- `tests/api/test_cases.py` verifies scope acknowledgment, case CRUD, entity CRUD, domain and URL validation, duplicate protection, cascading case deletion, and restart persistence against an isolated temporary data directory.
- `scripts/smoke.sh` verifies the Docker stack can create a scoped case through the web proxy, add domain and URL entities, restart the API container, and read the persisted entities.

## Milestone 3: Passive Enrichment

Status: Complete.

Deliverables:

- DNS lookup.
- RDAP lookup.
- HTTP status.
- Redirect chain.
- TLS certificate summary.
- Security headers.
- Page title.
- robots.txt and sitemap checks.

Acceptance:

- User can run enrichment for a domain or URL.
- Results are stored as enrichment runs.
- Failed modules report clear errors without breaking the case.

Verification:

- The API exposes SQLite-backed enrichment run endpoints for case and entity run history.
- Domain and URL enrichment derives a passive target and records DNS, RDAP, HTTP status, redirect chain, TLS certificate, security header, page title, robots.txt, and sitemap module results.
- Individual module failures are stored with clear error messages while the enrichment run remains available for review.
- The web app renders enrichment controls, per-entity latest run status, and module-level result summaries.
- `tests/api/test_enrichment.py` verifies stored run results, failed-module error reporting, URL target derivation, unsupported entity rejection, and restart persistence against an isolated temporary data directory.
- `scripts/smoke.sh` verifies the Docker stack can create a scoped case through the web proxy, add domain and URL entities, run passive enrichment for the domain entity, restart the API container, and read persisted entities.

## Milestone 4: Public News Trend Monitoring

Deliverables:

- Keyword set management for scoped public news monitoring.
- Brave Search API or similar public news/search provider integration.
- Public news/search ingestion run records.
- Result review queue with source URL, publisher, title, snippet, published date when available, retrieval timestamp, and query keyword.
- Basic trend grouping by keyword, source, time window, and repeated theme.
- Save relevant public news results as evidence links.

Acceptance:

- User can run a scoped keyword scan for scam, fraud, crime, impersonation, or adjacent public-interest terms.
- Returned public news/search results are stored for analyst review without making unsupported conclusions.
- User can save relevant results as evidence.
- User can view a basic trend summary with source attribution and confidence-aware language.

## Milestone 5: Evidence Capture

Deliverables:

- Screenshot capture.
- Evidence records.
- Local artifact storage.
- File hashing.
- Evidence-to-entity and evidence-to-finding links.

Acceptance:

- User can capture screenshot evidence.
- Evidence files are stored locally.
- Evidence metadata is visible in the case.

## Milestone 6: Findings

Deliverables:

- Finding creation.
- Generated finding suggestions.
- Confidence labels.
- Severity labels.
- Manual verification status.

Acceptance:

- User can turn enrichment results into findings.
- User can edit confidence and severity.
- Findings show linked evidence.

## Milestone 7: Reports

Deliverables:

- Markdown report export.
- JSON case bundle export.
- Report preview.
- Evidence table.
- Timeline section.
- Recommendations section.

Acceptance:

- User can export a complete Markdown report.
- Export includes scope, methodology, findings, evidence, and recommendations.

## Milestone 8: Graph And Timeline

Deliverables:

- Relationship graph.
- Timeline view.
- Automatic timeline events.
- Relationship records.

Acceptance:

- User can see how case entities, evidence, and findings connect.
- User can review case activity in chronological order.

## Milestone 9: Change Monitoring

Deliverables:

- Scheduled re-checks.
- Change detection.
- Change timeline events.
- In-app alerts.

Acceptance:

- User can monitor a domain or URL.
- The app records meaningful changes between checks.
