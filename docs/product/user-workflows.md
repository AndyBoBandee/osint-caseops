# User Workflows

## Workflow 1: Domain Review

1. Create a case with the type `Business exposure review`, `Vendor review`, or `Scam review`.
2. Confirm the scope is public-source and passive-only.
3. Add a domain entity.
4. Run domain enrichment.
5. Review DNS, RDAP, TLS, HTTP, security header, robots.txt, and sitemap results.
6. Save relevant evidence.
7. Create findings with confidence labels.
8. Export a Markdown report.

## Workflow 2: Suspicious URL Review

1. Create a scam or fraud review case.
2. Add a URL entity.
3. Capture HTTP status, redirect chain, page title, screenshot, and metadata.
4. Review whether the page redirects, imitates a brand, lacks contact details, or uses suspicious infrastructure.
5. Save screenshot evidence.
6. Add analyst notes and confidence labels.
7. Export a research packet.

## Workflow 3: Owned Asset Exposure Check

1. Create an authorized security or owned-business case.
2. Add owned domains and related URLs.
3. Run passive enrichment.
4. Review DNS, TLS, headers, public page metadata, and redirects.
5. Capture findings related to misconfiguration or stale assets.
6. Export cleanup recommendations.

## Workflow 4: Vendor Risk Snapshot

1. Create a vendor review case.
2. Add vendor domain and public website URLs.
3. Run passive checks.
4. Review domain age, TLS details, redirects, security headers, and policy-page presence.
5. Add findings and notes.
6. Export a lightweight summary.

## Workflow 5: Change Monitoring

1. Select a domain or URL already in a case.
2. Enable scheduled passive re-checks.
3. Compare new enrichment results to previous snapshots.
4. Record changes in the timeline.
5. Promote important changes into findings.
6. Include change history in reports.
