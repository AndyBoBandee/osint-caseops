SHELL := /bin/bash

API_DIR := apps/api
WEB_DIR := apps/web
DOCKER_DIR := infra/docker

.PHONY: help bootstrap dev api web ios-build mac-build mac-run test-fast test check smoke docker-up docker-down docker-logs

help:
	@printf "Fraud Monitor commands\n\n"
	@printf "  make bootstrap    Install API and web dependencies\n"
	@printf "  make dev          Start API reload and Next dev together\n"
	@printf "  make api          Start only the FastAPI dev server\n"
	@printf "  make web          Start only the Next.js dev server\n"
	@printf "  make ios-build    Compile the native SwiftUI Fraud Monitor app package\n"
	@printf "  make mac-build    Compile the native macOS Fraud Monitor app\n"
	@printf "  make mac-run      Run the native macOS Fraud Monitor app\n"
	@printf "  make test-fast    Run API tests and web lint\n"
	@printf "  make test         Run fast checks plus web build\n"
	@printf "  make check        Run repo hygiene, tests, build, audit, and Compose config\n"
	@printf "  make smoke        Run full Docker Compose smoke check\n"
	@printf "  make docker-up    Start the Docker Compose stack\n"
	@printf "  make docker-down  Stop the Docker Compose stack\n"
	@printf "  make docker-logs  Show recent Docker Compose logs\n"

bootstrap:
	cd $(API_DIR) && uv sync
	cd $(WEB_DIR) && npm ci

dev:
	./scripts/dev.sh

api:
	cd $(API_DIR) && uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

web:
	./scripts/web.sh

ios-build:
	swift build --package-path apps/ios/FraudMonitor --product FraudMonitorApp

mac-build:
	swift build --package-path apps/ios/FraudMonitor --product FraudMonitorMac

mac-run:
	swift run --package-path apps/ios/FraudMonitor FraudMonitorMac

test-fast:
	cd $(API_DIR) && uv run pytest ../../tests/api
	cd $(WEB_DIR) && npm run lint

test: test-fast
	cd $(WEB_DIR) && npm run build

check:
	git diff --check
	rg -n '[[:blank:]]$$' README.md AGENTS.md docs Makefile scripts; test $$? -eq 1
	rg -n 'TO[D]O|TB[D]|FIX[M]E' README.md AGENTS.md docs apps/api apps/web infra tests Makefile scripts --glob '!**/.venv/**' --glob '!**/node_modules/**' --glob '!**/.next/**'; test $$? -eq 1
	$(MAKE) test
	cd $(WEB_DIR) && npm audit --audit-level=moderate
	cd $(DOCKER_DIR) && docker compose config >/dev/null

smoke:
	./scripts/smoke.sh

docker-up:
	cd $(DOCKER_DIR) && docker compose up -d --build

docker-down:
	cd $(DOCKER_DIR) && docker compose down

docker-logs:
	cd $(DOCKER_DIR) && docker compose logs --no-color --tail=160
