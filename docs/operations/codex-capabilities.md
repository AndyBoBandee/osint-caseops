# Codex Capability Guide

Use this guide to route Codex work in OSINT CaseOps without adding repo-local skill files or nested `AGENTS.md` files. The root `AGENTS.md` remains the contributor entry point unless a subtree later needs genuinely different rules.

## Always Start With Repo Context

- Read `AGENTS.md` and the relevant docs under `docs/project`, `docs/product`, `docs/security`, or `docs/architecture`.
- Treat `.venv/`, `node_modules/`, `.next/`, `.pytest_cache/`, `__pycache__/`, `.DS_Store`, and local SQLite files under `data/` as ignored local artifacts.
- Keep real case data, screenshots, exported reports, API keys, and enrichment outputs out of Git.

## Use By Task Type

| Task | Capability | Use When |
| --- | --- | --- |
| React or Next.js implementation | Build Web Apps, React best practices | Building or refactoring `apps/web`, especially layout, state, accessibility, and performance-sensitive components. |
| Frontend visual smoke checks | Browser or Playwright | Opening local `localhost` targets, capturing screenshots, checking responsive layout, and reproducing UI regressions. |
| Local repo validation | Shell commands | Running `git diff --check`, API tests, web lint/build, `npm audit`, and Docker Compose validation. |
| GitHub PR or CI work | GitHub | Inspecting pull requests, review comments, failed checks, CI logs, branches, and issue context. |
| Security-sensitive changes | Codex Security | Reviewing enrichment, reporting, breach-adjacent, scan-adjacent, person-related, auth, storage, or external-request changes. |
| OpenAI API work | OpenAI docs | Adding or changing OpenAI models, prompts, API usage, SDK calls, or safety guidance. |

## Currently Unneeded

Do not route normal OSINT CaseOps work through Stripe, Supabase, Canva, Gmail, Google Calendar, iOS, macOS, or Game Studio capabilities unless the product scope changes to include payments, hosted Postgres, marketing assets, inbox/calendar workflows, native apps, or game features.

Do not add shadcn-specific workflow unless the repo adopts shadcn UI and adds `components.json`.

## Baseline Checks

Run these checks before committing repo hygiene or capability guidance changes:

```sh
git diff --check
rg -n '[[:blank:]]$' README.md AGENTS.md docs Makefile scripts
rg -n 'TO[D]O|TB[D]|FIX[M]E' README.md AGENTS.md docs apps/api apps/web infra tests Makefile scripts
cd apps/api && uv run pytest ../../tests/api
cd apps/web && npm run lint
cd apps/web && npm run build
cd apps/web && npm audit --audit-level=moderate
cd infra/docker && docker compose config
```
