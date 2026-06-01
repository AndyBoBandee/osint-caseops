# Fraud Monitor

A local-first dashboard for monitoring public results about one keyword: `fraud`.

This repository is being narrowed back to a focused app foundation. The current product surface is a dashboard that can run on-demand and scheduled public-search jobs for the fixed keyword `fraud`, store results locally in SQLite, and let an analyst review or save source links as evidence.

## What It Does

- Runs one fixed keyword monitor for `fraud`.
- Supports manual runs and a local cron-style scheduler while the API process is running.
- Uses Brave News Search as the primary live provider when `BRAVE_SEARCH_API_KEY` is configured,
  with Hacker News Algolia as the no-key fallback.
- Stores runs, results, review status, trend groups, and evidence links in local SQLite.
- Validates provider configuration and separates fixture-only test mode from real provider runs.
- Exports reviewed local data as Markdown reports or JSON audit bundles.
- Runs locally by default with FastAPI, Next.js, SQLite, and Docker Compose.

## Why It Exists

The broader OSINT CaseOps idea is still useful, but the app now starts from one concrete workflow: monitor public fraud reporting, make every provider run visible, and keep the review queue local and understandable.

## Responsible Use

This project is intended for lawful, ethical, public-source research. It should not be used for stalking, harassment, doxxing, credential harvesting, unauthorized scanning, or researching private individuals without a legitimate purpose. Users are responsible for complying with applicable laws, platform terms, and ethical research standards.

## Quick Start

Install dependencies:

```sh
make bootstrap
```

Run the fast local development stack:

```sh
make dev
```

Useful checks:

```sh
make test-fast
make test
make check
make smoke
```

`make dev` runs the API at `http://127.0.0.1:8000` and the web app at `http://127.0.0.1:3000`. `make smoke` runs the Docker Compose stack, verifies API, SQLite, the Fraud Monitor dashboard, and the schedule API without making live provider calls, then shuts the stack down.

For a first local pilot, follow `docs/operations/pilot-readiness.md`.

## Project Layout

- `apps/web/`: Next.js frontend.
- `apps/api/`: FastAPI backend.
- `docs/`: product, architecture, security, brand, and planning documentation.
- `data/`: local runtime data. Do not commit real case data or exports.
- `infra/docker/`: Docker Compose configuration.
- `scripts/`: root helper scripts used by `make` commands.
- `tests/`: API and end-to-end tests.

## Example Workflows

- Run an on-demand `fraud` search across configured public providers.
- Enable or disable local scheduled `fraud` scans.
- Review stored public results and mark them pending, relevant, or not relevant.
- Save source links as evidence records for later analysis.
- Export reviewed results as a Markdown report or JSON audit bundle.

## Documentation

Start with:

- `docs/operations/pilot-readiness.md`
- `docs/operations/local-development.md`
- `docs/planning/milestones.md`
- `docs/project/brand-book.md`
- `docs/project/scope.md`
- `docs/product/mvp.md`
- `docs/product/ui-language.md`
- `docs/product/report-style-guide.md`
- `docs/security/responsible-use.md`

## Contributing

Contributions are welcome around provider adapters, scheduler reliability, evidence handling, accessibility, tests, and documentation. Features that enable harassment, doxxing, credential harvesting, unauthorized access, or invasive profiling will not be accepted.

## Roadmap

See `docs/project/roadmap.md` and `docs/planning/milestones.md`.
