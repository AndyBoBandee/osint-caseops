# Safety Guardrails

## Scope Gate

Every case must start with a scope category:

- Self-audit.
- Owned business audit.
- Authorized security review.
- Scam or fraud review.
- Public-interest research.
- Vendor review.
- Brand protection.

The app should store the selected scope and show it in exported reports.

## Module Controls

MVP modules are passive by default. They should not:

- Attempt authentication bypass.
- Submit forms.
- Guess hidden paths aggressively.
- Brute force subdomains.
- Crawl private areas.
- Collect credentials.
- Use stolen or leaked private data.

Public news monitoring must:

- Restrict scans to scoped scam, fraud, crime, impersonation, or adjacent public-interest terms.
- Store provider results for analyst review instead of asserting that a result proves wrongdoing.
- Show source attribution and confidence-aware trend language.
- Save only public source links as milestone 4 evidence, with full artifact capture deferred to the
  evidence milestone.

## Sensitive Entity Controls

The MVP should avoid private-person investigation workflows.

If person-related entities are added later, the product should require:

- Clear purpose.
- Scope acknowledgment.
- Export warnings.
- Stronger redaction support.
- Disabled automated enrichment by default.

## Reporting Controls

Reports should include:

- Case scope.
- Methodology.
- Source URLs.
- Evidence timestamps.
- Confidence labels.
- Clear distinction between observed facts and analyst interpretation.
- Limitations and recommended next steps.

Reports should warn users to redact sensitive data before sharing.

See `docs/product/report-style-guide.md` for report structure and approved finding language.

## Auditability

The system should keep timeline records for:

- Case creation.
- Entity creation.
- Enrichment runs.
- Evidence capture.
- Finding creation.
- Report export.
- Scope changes.

## Future Safety Reviews

Features requiring a safety review before implementation:

- Username enumeration.
- Phone-number enrichment.
- Breach-check integrations.
- Shodan or scan-adjacent integrations.
- Social-profile automation.
- Team sharing.
- Public report publishing.

## Brand Safety Review

Before shipping a page, feature, or document, check:

- Is the use case ethical and scoped?
- Is evidence connected to findings?
- Is confidence visible with a text label?
- Could the feature be misread as harassment, doxxing, or invasive profiling?
- Does the user understand the limitation?
