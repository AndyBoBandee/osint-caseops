# MVP Definition

## MVP Thesis

The MVP should prove that OSINT CaseOps can support one complete, ethical, local-first investigation workflow from case creation to report export.

The first workflow is domain and URL investigation for scam, vendor, brand, and small-business exposure review.

## MVP Brand Promise

OSINT CaseOps helps users investigate domains and URLs through scoped cases, preserved evidence, confidence-rated findings, and exportable reports.

## Primary User

The primary MVP user is a technically comfortable individual or small team that needs to review a public domain or URL without using an enterprise investigation platform.

Examples:

- Small-business owner checking public exposure.
- Security hobbyist reviewing owned assets.
- Analyst reviewing a suspicious vendor domain.
- Researcher preserving public evidence for a scam review.

## Core User Journey

1. User creates a case.
2. User selects a lawful scope category.
3. User adds a domain or URL.
4. System runs passive enrichment.
5. User reviews results and generated findings.
6. User captures or confirms evidence.
7. User adds notes and confidence labels.
8. User exports a Markdown report.

## Required MVP Screens

- Case list.
- Create case.
- Case overview.
- Entity detail.
- Enrichment results.
- Evidence list.
- Finding editor.
- Relationship graph.
- Timeline.
- Report preview/export.
- Responsible-use acknowledgment.

## Homepage Copy Direction

Default headline:

> Turn public-source research into clear, defensible reports.

Default subheadline:

> OSINT CaseOps is a local-first, open-source workbench for ethical OSINT investigations. Organize cases, track entities, capture evidence, rate confidence, map relationships, and export reports.

Primary action: `Create case`

Secondary action: `View documentation`

## Required MVP Backend Features

- CRUD for cases.
- CRUD for entities.
- CRUD for evidence.
- CRUD for findings.
- Relationship persistence.
- Timeline event generation.
- Enrichment run tracking.
- Markdown report generation.
- JSON case bundle export.

## Required MVP Enrichment

- DNS lookup.
- RDAP lookup.
- HTTP status.
- Redirect chain.
- TLS certificate summary.
- Security headers.
- Page title.
- Screenshot capture.
- robots.txt check.
- sitemap.xml check.

## Acceptance Criteria

The MVP is complete when a user can run the app locally, create a scoped case, investigate a domain or URL, preserve evidence, add findings, view relationships and timeline events, and export a Markdown report without leaving the app.
