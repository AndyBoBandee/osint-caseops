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
DASHBOARD_FILE="$(mktemp)"
SCHEDULE_FILE="$(mktemp)"
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
    "${DASHBOARD_FILE}" \
    "${SCHEDULE_FILE}"
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
grep -q 'Fraud Monitor' "${WEB_FILE}"
grep -q 'fraud' "${WEB_FILE}"

curl -fsS "${WEB_URL}/api/backend/fraud-monitor/dashboard" >"${DASHBOARD_FILE}"
grep -q '"keyword":"fraud"' "${DASHBOARD_FILE}"
grep -q '"enabled":false' "${DASHBOARD_FILE}"
grep -q '"interval_minutes":60' "${DASHBOARD_FILE}"
grep -q '"providers":' "${DASHBOARD_FILE}"

curl -fsS -X PATCH "${WEB_URL}/api/backend/fraud-monitor/schedule" \
  -H "content-type: application/json" \
  --data-binary '{"enabled":false,"interval_minutes":60}' \
  >"${SCHEDULE_FILE}"
grep -q '"enabled":false' "${SCHEDULE_FILE}"
grep -q '"interval_minutes":60' "${SCHEDULE_FILE}"

echo "API health: $(cat "${API_HEALTH_FILE}")"
echo "DB health: $(cat "${DB_HEALTH_FILE}")"
echo "Web dashboard: Fraud Monitor rendered"
echo "Fraud monitor smoke: dashboard bootstrap and schedule API verified without live provider calls"
