# Source Pack v1

`fraud-intel-source-pack-v1` adds trusted source metadata and adapters to the existing Fraud Monitor workflow. The fixed default keyword remains `fraud`.

## Provider Registry

The provider registry exposes:

- Provider ID and display name.
- Source type and source confidence.
- Enabled/default-enabled state.
- API-key requirement.
- Fixture-mode support.
- Covered fraud categories.
- Request cap, timeout, and safety notes.

Existing provider IDs remain supported: `gdelt`, `google_news_rss`, `hn_algolia`, `brave`, and `fixture`. `gdelt` remains a compatibility alias for the GDELT DOC adapter.

## Tier 1 Providers

- `doj_news`: DOJ press-release API metadata.
- `cfpb_complaints`: public CFPB complaint search metadata, without consumer narratives.
- `gdelt_doc`: GDELT DOC article metadata.
- `fincen_advisories`: FinCEN advisory/key-term metadata.
- `ftc_consumer_sentinel_import`: local import of analyst-provided Consumer Sentinel annual CSV data.

## Tier 2 Stubs

These providers are documented but disabled until implemented:

- `sec_litigation_releases`
- `irs_ci_press_releases`
- `uspis_fraud`

If configured, they report a clear unsupported-provider message rather than making network requests.

## Storage Boundaries

Fraud Monitor stores titles, URLs, publisher/source names, dates, snippets or summaries, taxonomy tags, source confidence, and analyst notes. It does not store full copyrighted news article bodies, private-person profiles, account numbers, SSNs, phone numbers, addresses, or login-gated data.
