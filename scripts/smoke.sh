#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_DIR="${ROOT_DIR}/infra/docker"
API_HEALTH_URL="http://127.0.0.1:8000/health"
DB_HEALTH_URL="http://127.0.0.1:8000/health/db"
WEB_URL="http://127.0.0.1:3000"
API_HEALTH_FILE="$(mktemp)"
DB_HEALTH_FILE="$(mktemp)"
WEB_FILE="$(mktemp)"
CASE_FILE="$(mktemp)"
DOMAIN_ENTITY_FILE="$(mktemp)"
URL_ENTITY_FILE="$(mktemp)"
ENTITIES_FILE="$(mktemp)"
CLEANED_UP=0
READY=0

cleanup() {
  local status=$?
  if [[ "${CLEANED_UP}" -eq 1 ]]; then
    exit "${status}"
  fi
  CLEANED_UP=1

  rm -f \
    "${API_HEALTH_FILE}" \
    "${DB_HEALTH_FILE}" \
    "${WEB_FILE}" \
    "${CASE_FILE}" \
    "${DOMAIN_ENTITY_FILE}" \
    "${URL_ENTITY_FILE}" \
    "${ENTITIES_FILE}"
  cd "${COMPOSE_DIR}"
  docker compose down
  exit "${status}"
}

trap cleanup EXIT INT TERM

cd "${COMPOSE_DIR}"
docker compose up -d --build

for _ in $(seq 1 60); do
  if curl -fs "${API_HEALTH_URL}" >"${API_HEALTH_FILE}" \
    && curl -fs "${DB_HEALTH_URL}" >"${DB_HEALTH_FILE}" \
    && curl -fs "${WEB_URL}" >"${WEB_FILE}"; then
    READY=1
    break
  fi
  sleep 1
done

if [[ "${READY}" -ne 1 ]]; then
  docker compose logs --no-color --tail=180
  echo "Smoke check failed: services did not become ready." >&2
  exit 1
fi

grep -q '"status":"ok"' "${API_HEALTH_FILE}"
grep -q '"service":"osint-caseops-api"' "${API_HEALTH_FILE}"
grep -q '"status":"ok"' "${DB_HEALTH_FILE}"
grep -q '"database":"/workspace/data/osint_caseops.sqlite3"' "${DB_HEALTH_FILE}"
grep -q 'API <!-- -->online' "${WEB_FILE}"
grep -q 'Case workbench' "${WEB_FILE}"

CASE_ID="$(
  curl -fsS "${WEB_URL}/api/backend/cases" \
    -H "content-type: application/json" \
    --data-binary '{
      "title": "Smoke Vendor Review",
      "objective": "Verify milestone 2 case and entity persistence.",
      "scope_category": "Vendor review",
      "scope_notes": "Passive public-source review only.",
      "case_type": "Vendor risk snapshot",
      "scope_acknowledged": true,
      "tags": ["smoke", "milestone-2"],
      "analyst_notes": "Created by smoke check."
    }' \
    >"${CASE_FILE}"
  python3 -c 'import json, sys; print(json.load(open(sys.argv[1]))["id"])' "${CASE_FILE}"
)"

curl -fsS "${WEB_URL}/api/backend/cases/${CASE_ID}/entities" \
  -H "content-type: application/json" \
  --data-binary '{
    "type": "domain",
    "value": "Example.COM.",
    "confidence": "medium",
    "tags": ["root"],
    "notes": "Smoke domain."
  }' \
  >"${DOMAIN_ENTITY_FILE}"

curl -fsS "${WEB_URL}/api/backend/cases/${CASE_ID}/entities" \
  -H "content-type: application/json" \
  --data-binary '{
    "type": "url",
    "value": "HTTPS://Example.com/login?next=home#ignored",
    "display_name": "Login URL",
    "confidence": "low"
  }' \
  >"${URL_ENTITY_FILE}"

grep -q '"value":"example.com"' "${DOMAIN_ENTITY_FILE}"
grep -q '"value":"https://example.com/login?next=home"' "${URL_ENTITY_FILE}"

docker compose restart api >/dev/null

READY=0
for _ in $(seq 1 60); do
  if curl -fs "${API_HEALTH_URL}" >"${API_HEALTH_FILE}"; then
    READY=1
    break
  fi
  sleep 1
done

if [[ "${READY}" -ne 1 ]]; then
  docker compose logs --no-color --tail=180
  echo "Smoke check failed: API did not become ready after restart." >&2
  exit 1
fi

curl -fsS "${WEB_URL}/api/backend/cases/${CASE_ID}/entities" >"${ENTITIES_FILE}"
grep -q '"value":"example.com"' "${ENTITIES_FILE}"
grep -q '"value":"https://example.com/login?next=home"' "${ENTITIES_FILE}"

echo "API health: $(cat "${API_HEALTH_FILE}")"
echo "DB health: $(cat "${DB_HEALTH_FILE}")"
echo "Web health: API online"
echo "Milestone 2 workflow: scoped case, domain entity, URL entity, restart persistence"
