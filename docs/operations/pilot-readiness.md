# Pilot Readiness

This checklist is the operator-facing path for the current Fraud Monitor product. Legacy OSINT
CaseOps case, entity, graph, timeline, and broad enrichment workflows are reference material unless
they are explicitly reintroduced in `docs/planning/milestones.md`.

## Local Operator Setup Checklist

1. Install dependencies from the repo root:

   ```sh
   make bootstrap
   ```

2. Start the local app:

   ```sh
   make dev
   ```

3. Open `http://127.0.0.1:3000`.
4. Confirm the dashboard shows `API online`.
5. Review provider configuration in the Providers panel.
6. Run a manual scan with `Run now`.
7. Review stored public results and mark each reviewed item `relevant` or `not relevant`.
8. Save useful source links as evidence with analyst notes.
9. Export the reviewed local data with `Export Markdown` or `Export JSON`.
10. Stop the dev process when the local review is complete.

## Configuration Validation

The API exposes provider validation at:

```text
GET /fraud-monitor/configuration/validation
```

The dashboard also includes this validation in the Providers panel. A pilot configuration is ready
when:

- At least one provider is `ready`.
- `brave` is only configured when `BRAVE_SEARCH_API_KEY` is available.
- `fixture` is only used for tests or smoke checks.
- Unknown provider names are removed from `OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS`.

For a Brave-backed local pilot, keep the key outside Git and export it before starting the app:

```sh
export BRAVE_SEARCH_API_KEY="your-local-key"
export OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS=brave,hn_algolia
make dev
```

Fixture mode is deterministic and local-test oriented:

```sh
OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER=1
OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS=fixture
```

Do not use fixture exports as real public-source findings.

## Data Retention And Cleanup

Local runtime data lives under `data/` by default, or under `OSINT_CASEOPS_DATA_DIR` when that
environment variable is set. Do not commit real case data, exported reports, screenshots, SQLite
files, or API keys.

Before deleting data, export any reviewed results that must be retained:

```text
Export Markdown
Export JSON
```

Then stop the app and remove only the intended local runtime directory. For the default data path:

```sh
rm -f data/osint_caseops.sqlite3
rm -rf data/exports/*
rm -rf data/tmp/*
```

Keep `data/cases/.gitkeep`, `data/exports/.gitkeep`, and `data/tmp/.gitkeep` in place.

## Release Checklist

Run these checks from a clean checkout before calling a pilot build ready:

```sh
make bootstrap
make check
make smoke
```

Review the release for:

- Privacy: no real case data, exports, screenshots, SQLite files, or API keys in Git.
- Safety: provider behavior remains passive public-source HTTP requests only.
- Local storage: runtime data stays under `data/` or the configured local data directory.
- Fixture separation: fixture mode is documented as test-only and not mixed with real findings.
- Export wording: reports keep source attribution, analyst-review language, and limitations.
- Docs routing: current work starts with Fraud Monitor docs and milestones, not the legacy OSINT
  workspace path.
