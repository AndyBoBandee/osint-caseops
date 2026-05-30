# Repository Guidelines

## Project Structure & Module Organization

This repository is a local-first OSINT workbench monorepo. Brand, voice, vocabulary, and safety rules live in `docs/project/brand-book.md`.

- `apps/web/`: planned Next.js frontend. UI source should live under `apps/web/src/`.
- `apps/api/`: planned FastAPI backend. API code should live under `apps/api/app/`.
- `docs/`: project, product, architecture, security, operations, and planning docs.
- `data/`: local runtime data for cases, exports, and temporary files. Do not commit real investigation data.
- `infra/docker/`: Docker Compose and container configuration.
- `packages/shared-schemas/`: shared API/schema contracts when needed.
- `tests/`: API, end-to-end, and fixture tests.

## Build, Test, and Development Commands

Use these commands for local development:

```sh
cd apps/api && uv run uvicorn app.main:app --reload
cd apps/api && uv run pytest ../../tests/api
cd apps/web && npm run dev
cd apps/web && npm run lint
cd apps/web && npm run build
cd infra/docker && docker compose up --build
```

The web app runs on `http://127.0.0.1:3000` by default. The API runs on `http://127.0.0.1:8000` and exposes `/health` and `/health/db`.

For Codex skill and plugin routing, see `docs/operations/codex-capabilities.md`.

## Coding Style & Naming Conventions

Use concise, typed code and keep module boundaries clear. Python modules should use `snake_case`; React components should use `PascalCase`; shared TypeScript types should use `PascalCase`. Use two-space indentation for TypeScript/React and four-space indentation for Python. Prefer explicit names such as `enrichment_runs`, `case_reports`, and `evidence_records` over abbreviations.

## Brand, Voice & Vocabulary

Use clear, calm, professional language. Prefer `case`, `entity`, `finding`, `evidence`, `source`, `confidence`, `timeline`, `relationship`, `scope`, `public-source research`, `local-first`, `report`, `enrichment`, and `analyst notes`. Avoid people-search, surveillance, exploit, or aggressive security phrasing unless quoting the brand book or writing prohibited-use guidance.

## Testing Guidelines

Place backend tests in `tests/api/`, browser or workflow tests in `tests/e2e/`, and reusable fixtures in `tests/fixtures/`. Name tests after behavior, such as `test_create_case_requires_scope.py` or `case-report-export.spec.ts`. Network-backed enrichment tests should be isolated from deterministic unit tests.

## Commit & Pull Request Guidelines

This repository has active Git history on `main`. Keep commits small and use Conventional Commit-style messages, for example `docs: add safety guardrails` or `feat(api): add case model`. Pull requests should include a short summary, linked issue if applicable, test results, screenshots for UI changes, and notes about any safety, privacy, or data-storage impact.

## Security & Configuration Tips

Keep OSINT work passive by default. Never commit real case data, screenshots, API keys, or exported reports. New enrichment, reporting, breach-related, scan-adjacent, or person-related work must document external requests, rate limits, safety limits, and responsible-use constraints before implementation.
