# Roadmap

Fraud Monitor is the current product direction. It is a focused, local-first
workflow for passive public-source monitoring of the fixed keyword `fraud`,
analyst review, and evidence-link saving.

The broader OSINT CaseOps case, entity, enrichment, relationship, timeline, and
report workflow is legacy direction unless explicitly reintroduced.

## Phase 1: Local Foundation

Goal: keep the app easy to run, verify, and reason about locally.

Deliverables:

- Monorepo structure.
- Next.js web app shell.
- FastAPI backend shell.
- SQLite database setup.
- Docker Compose for local development.
- Health checks.
- Responsible-use documentation.

## Phase 2: Fraud Monitor Workflow

Goal: make the first screen a complete fraud-monitoring workbench.

Deliverables:

- Fraud Monitor dashboard.
- Fixed keyword `fraud`.
- Manual run control.
- Local schedule control.
- Provider readiness and runtime status.
- Job history.
- Stored public results.
- Review queue with pending, relevant, and not relevant states.

## Phase 3: Evidence And Review Operations

Goal: help analysts work stored results into defensible local evidence.

Deliverables:

- Evidence-link saving from public results.
- Analyst notes.
- Review filters by status, provider, and evidence state.
- Result search and sort controls.
- Editable evidence notes.
- Bulk review actions with clear user intent.
- Duplicate and already-saved indicators.

## Phase 4: Provider Quality And Trends

Goal: make provider behavior and trend summaries useful without overclaiming.

Deliverables:

- Provider status classification.
- Timeout and partial-failure visibility.
- Provider request-limit documentation.
- Safer scheduled-run retry/backoff behavior.
- Trend grouping by keyword, source, time window, and repeated theme.
- Source-quality and recency cues for analyst prioritization.

## Phase 5: Local Export And Audit Bundle

Goal: produce local outputs that are reviewable and portable without cloud sync.

Deliverables:

- Markdown export.
- JSON audit bundle.
- Evidence table.
- Provider and retrieval metadata.
- Scope and methodology section.
- Confidence-aware trend summary.

## Phase 6: Pilot Readiness

Goal: make the local Fraud Monitor workflow reliable enough for repeated use.

Deliverables:

- Setup checklist.
- Provider configuration validation.
- Fixture-provider test guidance.
- Data retention and cleanup guidance.
- Release checklist covering privacy, safety, local storage, and docs.
- Rendered dashboard QA for the primary workflow.
