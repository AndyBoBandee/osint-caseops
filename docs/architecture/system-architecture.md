# System Architecture

## Default Stack

- Frontend: Next.js and React. Tailwind CSS and shadcn/ui are candidates when the UI system needs them, but they are not part of the current foundation scaffold.
- Backend: Python FastAPI.
- Database: SQLite.
- Evidence storage: local filesystem.
- Browser capture: Playwright.
- Background jobs: lightweight API-process scheduler for the current fraud monitor slice; a separate worker can be added when job volume or reliability needs it.
- Graph UI: React Flow or Cytoscape.js.
- Local deployment: Docker Compose.

## Components

### Web App

The current web app provides a focused Fraud Monitor dashboard:

- Fixed keyword status for `fraud`.
- Run-now controls.
- Cron-style schedule controls.
- Provider status.
- Review queue.
- Job history.
- Trend groups.
- Provider configuration validation.
- Local Markdown and JSON exports.

The broader analyst workspace below is legacy reference direction unless explicitly reintroduced in
the Fraud Monitor roadmap:

- Case dashboard.
- Entity forms.
- Evidence and findings views.
- Relationship graph.
- Timeline.
- Report preview and export controls.
- Responsible-use acknowledgment flow.

### API

The API owns application logic:

- Fraud monitor dashboard, job, schedule, review, and evidence wrapper endpoints.
- Fraud monitor provider validation and local export endpoints.
- Case, entity, evidence, finding, and relationship endpoints.
- Enrichment orchestration.
- Report generation.
- Timeline event creation.
- Local storage path management.

### Database

SQLite stores structured investigation data:

- Active Fraud Monitor data: the system fraud-monitor case, news runs, news results, evidence links,
  schedule settings, jobs, and provider job mappings.
- Legacy/reference data model: cases, entities, findings, relationships, enrichment runs, timeline
  events, and report export metadata.

### Evidence Storage

The filesystem stores captured artifacts:

- Screenshots.
- HTML snapshots, if enabled.
- Downloaded public files, if enabled later.
- Generated reports.
- JSON case bundles.

### Enrichment Modules

Each enrichment module should accept a normalized entity input and return structured JSON containing:

- Module name.
- Input entity.
- Result payload.
- Confidence hints.
- Source metadata.
- Timestamp.
- Error details, if any.

## Runtime Flow

1. User creates or opens a case in the web app.
2. Web app calls the API to create entities and run enrichment.
3. API validates scope and dispatches allowed enrichment modules.
4. Enrichment results are stored in SQLite.
5. Evidence artifacts are written to the local evidence folder.
6. Findings are created manually or suggested from enrichment results.
7. Timeline events are generated for important case actions.
8. Reports are generated from the database and evidence references.

## Local-First Rules

- The app must not require a cloud account.
- Cases and evidence must be usable offline after capture.
- API integrations must be optional.
- External network requests must be visible to the user through enrichment run history.
- Sensitive data should stay in the local project data directory unless exported by the user.

## Brand And Status Semantics

The product should use a calm analyst-workspace visual direction. Avoid hacker cliches, fear-based status treatment, and visual patterns that suggest coercive surveillance.

Recommended color semantics:

- Deep Navy `#0B1220`: primary brand surfaces.
- Slate Blue `#1E3A5F`: navigation, cards, and secondary UI.
- Signal Cyan `#22D3EE`: active states, selected entities, graph highlights, and links.
- Verified Green `#22C55E`: confirmed findings and successful checks.
- Evidence Amber `#F59E0B`: medium confidence and review-needed states.
- Risk Red `#EF4444`: serious warnings and failed checks, used sparingly.
- Slate Gray `#64748B`: secondary text, low confidence, and subdued labels.

Confidence mapping:

- High: Verified Green.
- Medium: Evidence Amber.
- Low: Slate Gray.
- Unknown: outline or neutral gray.

Every status color must include a text label for accessibility.
