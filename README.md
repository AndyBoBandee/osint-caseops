# OSINT CaseOps

Turn public data into defensible intelligence.

OSINT CaseOps is a local-first, open-source workbench for ethical public-source research. It helps users create scoped cases, track entities, preserve evidence, rate confidence, map relationships, monitor changes, and export reports.

## What It Does

- Organizes public-source research around cases, scope, and objectives.
- Tracks entities such as domains, URLs, email addresses, IP addresses, and organizations.
- Preserves evidence with source links, timestamps, notes, screenshots, and hashes.
- Turns raw enrichment into confidence-rated findings and reports.
- Runs locally by default with FastAPI, Next.js, SQLite, and Docker Compose.

## Why It Exists

Many OSINT tools collect data, but fewer help users verify, preserve, explain, and report what they found. OSINT CaseOps focuses on structured, ethical, evidence-first work rather than raw data dumping.

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

`make dev` runs the API at `http://127.0.0.1:8000` and the web app at `http://127.0.0.1:3000`. `make smoke` runs the Docker Compose stack, verifies API, SQLite, and web-to-API health, then shuts the stack down.

## Project Layout

- `apps/web/`: Next.js frontend.
- `apps/api/`: FastAPI backend.
- `docs/`: product, architecture, security, brand, and planning documentation.
- `data/`: local runtime data. Do not commit real case data or exports.
- `infra/docker/`: Docker Compose configuration.
- `scripts/`: root helper scripts used by `make` commands.
- `tests/`: API and end-to-end tests.

## Example Workflows

- Domain and URL investigation.
- Scam and fraud review.
- Small-business exposure review.
- Vendor risk snapshot.
- Brand monitoring.
- Personal digital footprint audit.

## Documentation

Start with:

- `docs/project/brand-book.md`
- `docs/project/scope.md`
- `docs/product/mvp.md`
- `docs/product/ui-language.md`
- `docs/product/report-style-guide.md`
- `docs/security/responsible-use.md`

## Contributing

Contributions are welcome around case workflows, evidence handling, enrichment modules, reporting, accessibility, tests, and documentation. Features that enable harassment, doxxing, credential harvesting, unauthorized access, or invasive profiling will not be accepted.

## Roadmap

See `docs/project/roadmap.md` and `docs/planning/milestones.md`.
