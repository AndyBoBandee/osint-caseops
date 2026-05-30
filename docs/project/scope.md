# Project Scope

## In Scope

OSINT CaseOps will provide a local-first workbench for ethical public-source research workflows.

Core capabilities:

- Case creation and management.
- Scoped investigation objectives.
- Entity tracking for domains, URLs, email addresses, IP addresses, and organizations.
- Evidence capture with source URL, timestamp, screenshot path, notes, and hash.
- Finding creation with confidence and severity labels.
- Passive enrichment for domains and URLs.
- Passive public news/search monitoring for scoped scam, fraud, crime, impersonation, and public-interest risk keywords.
- Basic trend analysis across public news/search results by keyword, source, time window, and repeated theme.
- Relationship mapping between cases, entities, findings, and evidence.
- Case timeline.
- Markdown and JSON report export.
- Local storage through SQLite and a local evidence folder.
- Responsible-use policy and in-product safety acknowledgments.

## MVP Scope

The MVP should prove one strong workflow: domain and URL investigation for scam, vendor, brand, and small-business exposure review. It should not overpromise as an all-purpose investigation platform.

MVP entity types:

- Domain.
- URL.
- Email address, limited to domain extraction and MX lookup.
- IP address, limited to passive metadata.
- Organization, used as a case context entity.

MVP enrichment modules:

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
- Public news/search API lookup through Brave Search API or a similar provider, limited to scoped keyword discovery and analyst-reviewed trend summaries.

MVP news/search monitoring captures:

- Source URL.
- Publisher.
- Title.
- Snippet.
- Published date when available.
- Retrieval timestamp.
- Query keyword.

MVP exports:

- Markdown report.
- JSON case bundle.

## Explicitly Out Of MVP Scope

These features are out of scope for the first implementation:

- Facial recognition.
- Credential, password, or secret harvesting.
- Dark web scraping.
- Exploit scanning or vulnerability exploitation.
- Login-protected scraping.
- Automated fraud verdicts from news/search results without analyst review and cited evidence.
- Automated private-individual profiling.
- Phone-number enrichment.
- Crypto-wallet investigation.
- Username enumeration across social platforms.
- Breach-data searching without a legitimate user-provided API and safety review.
- Multi-user collaboration.
- Cloud sync.
- PDF export.
- Enterprise SIEM, SOAR, MISP, or OpenCTI replacement features.

## Safety Boundaries

The product should discourage abuse by design:

- Require scope selection before creating a case.
- Disable risky modules by default.
- Keep enrichment passive unless explicitly expanded later.
- Keep news/search monitoring limited to public sources, scoped keywords, and provider terms.
- Require source attribution and confidence-aware language for trend summaries.
- Warn before adding person-related entities.
- Make source URLs and evidence timestamps visible in reports.
- Avoid workflows that encourage harassment, doxxing, stalking, credential theft, or unauthorized security testing.
- Keep language calm, professional, and evidence-based.

## Success Criteria

The MVP is successful when a user can:

- Create a scoped case in under one minute.
- Add a domain or URL entity.
- Run passive enrichment.
- Run a scoped public news keyword scan.
- Capture a screenshot and evidence record.
- Review generated findings with confidence labels.
- Review a basic fraud trend summary with cited public sources.
- Add analyst notes.
- See a simple relationship graph and timeline.
- Export a usable Markdown report.
- Complete the workflow locally through Docker Compose.
