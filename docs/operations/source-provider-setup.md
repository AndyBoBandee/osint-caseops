# Source Provider Setup

Default local runs still use no-key providers:

```sh
OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS=gdelt,google_news_rss,hn_algolia
```

Add trusted source-pack providers by listing them explicitly:

```sh
OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS=gdelt,google_news_rss,hn_algolia,doj_news,cfpb_complaints,fincen_advisories
```

## Brave Detailed Search

Brave remains optional and only runs for detailed search:

```sh
BRAVE_SEARCH_API_KEY=...
```

Keep the key local and out of commits.

## FTC Consumer Sentinel Import

FTC Consumer Sentinel support is a local import path, not a live API call:

```sh
OSINT_CASEOPS_FTC_CONSUMER_SENTINEL_PATH=/path/to/consumer-sentinel.csv
OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS=ftc_consumer_sentinel_import
```

Use aggregate annual data files only. Do not import raw consumer narratives or private complaint details.

## Fixture Mode

Fixture mode remains separate from real provider runs:

```sh
OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER=1
OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS=fixture
```

Fixture records are deterministic test data and must not be used as real findings.

## Safety Limits

Provider calls are passive HTTP GET requests or local imports. Do not scrape login-gated sources, target private individuals, or collect sensitive personal data. Provider failures are shown in the dashboard and do not block successful providers from contributing results.
