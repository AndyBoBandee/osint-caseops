# Fraud Monitor Native Apps

This package contains the native SwiftUI operator surfaces for Fraud Monitor. The macOS app is the primary analyst workstation. The iOS app remains available as a companion status and review surface.

Both apps connect to the existing local FastAPI service and keep the backend, provider registry, SQLite data, review state, evidence saves, and trend APIs as the source of truth.

## Run Locally

1. Start the API from the repo root:

```sh
make api
```

For deterministic fixture-backed local runs:

```sh
OSINT_CASEOPS_DATA_DIR=/tmp/osint-caseops-mac-data \
OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER=1 \
OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS=fixture \
make api
```

2. Run the macOS analyst app:

```sh
make mac-run
```

You can also open `apps/ios/FraudMonitor/Package.swift` in Xcode and run the `FraudMonitorMac` product.

The default API base URL is:

```text
http://127.0.0.1:8000
```

You can change it in the macOS Settings window or the iOS Settings tab.

## macOS Analyst Workstation

- Sidebar workspace: Monitor, Review Queue, Trends, Providers, and Settings overview.
- Review Queue: dense desktop table, search/filter stored results, select a result with keyboard navigation, review classification/source metadata, mark relevance, and save evidence notes.
- Trends: inspect category, official-source, state, payment rail, and keyword summaries.
- Providers: inspect provider health, fixture warnings, and missing API-key state.
- Local API status: check `/health` and `/health/db`, see the active base URL, and copy launch commands without letting the app start or stop backend processes.
- Settings window: reconnect to a different API URL and review local-first constraints.

## Source-Pack And Trends QA

Run the operator QA script from the repo root when provider/trend behavior changes:

```sh
scripts/source_pack_trends_qa.sh
```

The script uses isolated local data directories, starts temporary API instances, and verifies fixture mode, configured no-key providers, and a DOJ official-source run. It checks provider health, stored classifications, trend summaries, review state, evidence-note save/edit, and Markdown/JSON exports.

## iOS Companion App

The iOS app keeps the compact tabbed workflow for quick monitoring and review on Simulator or device. Build it with:

```sh
make ios-build
```

Build the macOS app with:

```sh
make mac-build
```

Full iOS Simulator validation requires full Xcode with Simulator tools selected as the active developer directory.
