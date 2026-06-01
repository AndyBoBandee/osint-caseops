# Fraud Monitor Brand Book

Version: v0.2

Project status: focused local-first app foundation

## Brand Foundation

Brand name: Fraud Monitor

Fraud Monitor is a local-first dashboard for passive public-source monitoring of one fixed keyword: `fraud`.

The earlier OSINT CaseOps concept remains useful as provenance and longer-term product context, but Fraud Monitor is the active product direction, documentation name, and user-facing brand.

## Positioning

Fraud Monitor helps analysts run visible, repeatable public-search jobs for fraud-related reporting, review the returned sources, and save useful links as evidence in local storage.

It should feel:

- Calm.
- Professional.
- Methodical.
- Evidence-first.
- Local-first.
- Transparent about sources and limits.

It should not feel:

- Surveillance-oriented.
- Alarmist.
- Spy-themed.
- Aggressive.
- Like an automated verdict engine.
- Like a people-search product.

## Voice And Vocabulary

Use concise, plain language. Prefer:

- case
- source
- public-source research
- evidence
- finding
- confidence
- review
- trend
- timeline
- analyst notes
- local-first
- provider
- run
- report

Avoid aggressive or invasive phrasing unless writing prohibited-use guidance. Do not position the product as stalking, doxxing, credential discovery, active scanning, or private-individual profiling tooling.

## Product Promise

Primary promise:

> Monitor public fraud reporting, review sources, and keep evidence local.

Short description:

> Fraud Monitor is a local-first dashboard for running on-demand and scheduled public-source searches for the fixed keyword `fraud`, reviewing results, and saving source links as evidence.

Long description:

> Fraud Monitor helps analysts keep a focused review queue for public fraud reporting. It runs passive provider searches, records each run and result in local SQLite, shows provider status and trend groups, and keeps analyst review decisions visible. The product is designed for lawful, ethical, public-source research and does not make automated fraud verdicts.

## Current Product Surface

The current app surface is the Fraud Monitor dashboard:

- Fixed keyword: `fraud`.
- Manual run control.
- Local scheduler control while the API process is running.
- Provider readiness and job history.
- Recent public results.
- Analyst review status.
- Evidence-link saving.
- Provider configuration validation.
- Basic trend grouping.
- Markdown and JSON exports for reviewed local data.

Broader case, entity, graph, timeline, and report workflows are legacy OSINT CaseOps direction unless explicitly reintroduced into the Fraud Monitor roadmap.

## Responsible Use

Fraud Monitor is intended for lawful, ethical, passive public-source research. Users are responsible for complying with applicable laws, provider terms, and organizational policies.

The product should not support or encourage:

- Stalking.
- Harassment.
- Doxxing.
- Credential harvesting.
- Unauthorized access.
- Exploit scanning.
- Private-account scraping.
- Automated profiling of private individuals.
- Automated fraud verdicts without analyst review and cited evidence.

## UI Copy Patterns

Preferred labels:

- Run now
- Running
- Refresh
- Review queue
- Save evidence
- Mark relevant
- Mark not relevant
- Provider status
- Job history
- Trend groups
- Analyst note

Empty states should describe the next useful action without marketing language:

- "No fraud results are stored yet."
- "Run a scan to build fraud trend groups."
- "No fraud jobs have run yet."

Warnings should be firm and specific:

- "Start the API to run fraud scans."
- "Could not refresh dashboard."
- "No ready fraud monitor providers are configured."
- "A fraud monitor job is already running."

## Runtime Behavior

Fraud Monitor runs one job at a time. Manual overlap should show a clear `409 Conflict` message, and scheduled overlap should wait for the next scheduler tick without moving the next-run timestamp.

The `fixture` provider is test-only. It is available only when `OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER=1` is set and should not be described as a real public provider.

## Technical Naming Boundary

Do not rename stable technical identifiers solely for brand alignment. The repository may still contain names such as `osint-caseops-api`, `osint-caseops.css`, or historical OSINT CaseOps references where changing them would create churn without user-facing benefit.
