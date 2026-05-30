# Roadmap

## Phase 1: Foundation

Goal: establish the local project shell and core data model.

Deliverables:

- Monorepo structure.
- Next.js web app shell.
- FastAPI backend shell.
- SQLite database setup.
- Local evidence storage path.
- Docker Compose for local development.
- Responsible-use documentation.

## Phase 2: Case Workspace

Goal: create the core investigation workspace.

Deliverables:

- Case creation.
- Case dashboard.
- Entity creation.
- Notes and tags.
- Scope acknowledgment.
- Case status tracking.

## Phase 3: Domain And URL Enrichment

Goal: make the first workflow useful.

Deliverables:

- DNS lookup.
- RDAP lookup.
- HTTP status and redirect chain.
- TLS certificate summary.
- Security headers.
- Page title.
- Screenshot capture.
- robots.txt and sitemap.xml checks.
- Stored enrichment run results.

## Phase 4: Evidence And Findings

Goal: turn raw enrichment into defensible investigation output.

Deliverables:

- Evidence records.
- Screenshot storage.
- File hashing.
- Finding creation.
- Confidence labels.
- Severity labels.
- Source reliability labels.
- Manual verification marker.

## Phase 5: Reports

Goal: produce useful exports.

Deliverables:

- Markdown report export.
- JSON case bundle export.
- Report templates.
- Evidence table.
- Finding summaries.
- Recommendations section.

## Phase 6: Graph And Timeline

Goal: help users understand relationships and sequence.

Deliverables:

- Basic relationship graph.
- Case timeline.
- Entity-to-evidence links.
- Finding-to-evidence links.
- Relationship confidence labels.

## Phase 7: Change Monitoring

Goal: track changes over time for scoped assets.

Deliverables:

- Scheduled re-checks.
- DNS change detection.
- TLS certificate change detection.
- Redirect-chain change detection.
- Page title and header change detection.
- Screenshot comparison metadata.
- In-app change alerts.

## Phase 8: Optional Integrations

Goal: add API-based enrichment without compromising the local-first baseline.

Candidate integrations:

- VirusTotal.
- URLScan.io.
- AlienVault OTX.
- GreyNoise.
- GitHub public search.
- Have I Been Pwned.
- MISP export/import.
- OpenCTI export/import.

Integrations that touch breach, scanning, or sensitive-person data require explicit safety review before implementation.
