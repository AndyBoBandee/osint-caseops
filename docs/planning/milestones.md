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

## Milestone 3: Passive Enrichment

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

## Milestone 4: Evidence Capture

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

## Milestone 5: Findings

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

## Milestone 6: Reports

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

## Milestone 7: Graph And Timeline

Deliverables:

- Relationship graph.
- Timeline view.
- Automatic timeline events.
- Relationship records.

Acceptance:

- User can see how case entities, evidence, and findings connect.
- User can review case activity in chronological order.

## Milestone 8: Change Monitoring

Deliverables:

- Scheduled re-checks.
- Change detection.
- Change timeline events.
- In-app alerts.

Acceptance:

- User can monitor a domain or URL.
- The app records meaningful changes between checks.
