#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_DIR="${ROOT_DIR}/infra/docker"
API_HEALTH_URL="http://127.0.0.1:8000/health"
DB_HEALTH_URL="http://127.0.0.1:8000/health/db"
WEB_URL="http://127.0.0.1:3000"
SMOKE_DATA_DIR="${ROOT_DIR}/.smoke-data"
API_HEALTH_FILE="$(mktemp)"
DB_HEALTH_FILE="$(mktemp)"
WEB_FILE="$(mktemp)"
WEB_AFTER_FILE="$(mktemp)"
DASHBOARD_FILE="$(mktemp)"
SCHEDULE_FILE="$(mktemp)"
CONFIG_FILE="$(mktemp)"
JOB_FILE="$(mktemp)"
REVIEW_FILE="$(mktemp)"
EVIDENCE_FILE="$(mktemp)"
BULK_REVIEW_FILE="$(mktemp)"
NOTE_FILE="$(mktemp)"
JSON_EXPORT_FILE="$(mktemp)"
MARKDOWN_EXPORT_FILE="$(mktemp)"
SEARCH_FILE="$(mktemp)"
PAGED_FILE="$(mktemp)"
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
	    "${WEB_AFTER_FILE}" \
	    "${DASHBOARD_FILE}" \
	    "${SCHEDULE_FILE}" \
	    "${CONFIG_FILE}" \
	    "${JOB_FILE}" \
	    "${REVIEW_FILE}" \
	    "${EVIDENCE_FILE}" \
	    "${BULK_REVIEW_FILE}" \
	    "${NOTE_FILE}" \
	    "${JSON_EXPORT_FILE}" \
	    "${MARKDOWN_EXPORT_FILE}" \
	    "${SEARCH_FILE}" \
	    "${PAGED_FILE}"
	  rm -rf "${SMOKE_DATA_DIR}"
	  cd "${COMPOSE_DIR}"
	  docker compose down
	  exit "${status}"
}

trap cleanup EXIT INT TERM

rm -rf "${SMOKE_DATA_DIR}"
mkdir -p "${SMOKE_DATA_DIR}"
export OSINT_CASEOPS_DATA_DIR="/workspace/.smoke-data"
export OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER=1
export OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS=fixture

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
grep -q '"database":"/workspace/.smoke-data/osint_caseops.sqlite3"' "${DB_HEALTH_FILE}"
grep -q 'Fraud Monitor' "${WEB_FILE}"
grep -q 'fraud' "${WEB_FILE}"

curl -fsS "${WEB_URL}/api/backend/fraud-monitor/dashboard" >"${DASHBOARD_FILE}"
grep -q '"keyword":"fraud"' "${DASHBOARD_FILE}"
grep -q '"enabled":false' "${DASHBOARD_FILE}"
grep -q '"interval_minutes":60' "${DASHBOARD_FILE}"
grep -q '"name":"fixture"' "${DASHBOARD_FILE}"
grep -q '"status":"ready"' "${DASHBOARD_FILE}"
grep -q '"ready_provider_count":1' "${DASHBOARD_FILE}"
grep -q '"configuration_validation"' "${DASHBOARD_FILE}"

curl -fsS "${WEB_URL}/api/backend/fraud-monitor/configuration/validation" >"${CONFIG_FILE}"
grep -q '"is_valid":true' "${CONFIG_FILE}"
grep -q '"fixture_mode":true' "${CONFIG_FILE}"
grep -q '"provider":"fixture"' "${CONFIG_FILE}"
grep -q 'test-only' "${CONFIG_FILE}"

curl -fsS -X PATCH "${WEB_URL}/api/backend/fraud-monitor/schedule" \
  -H "content-type: application/json" \
  --data-binary '{"enabled":false,"interval_minutes":60}' \
  >"${SCHEDULE_FILE}"
grep -q '"enabled":false' "${SCHEDULE_FILE}"
grep -q '"interval_minutes":60' "${SCHEDULE_FILE}"

curl -fsS -X POST "${WEB_URL}/api/backend/fraud-monitor/jobs" >"${JOB_FILE}"
grep -q '"status":"success"' "${JOB_FILE}"
grep -q '"result_count":2' "${JOB_FILE}"

curl -fsS "${WEB_URL}/api/backend/fraud-monitor/dashboard" >"${DASHBOARD_FILE}"
grep -q '"provider":"fixture"' "${DASHBOARD_FILE}"
grep -q '"pending_results":2' "${DASHBOARD_FILE}"

curl -fsS "${WEB_URL}/api/backend/fraud-monitor/dashboard?limit=1" >"${PAGED_FILE}"
grep -q '"total_matching":2' "${PAGED_FILE}"
grep -q '"limit":1' "${PAGED_FILE}"
grep -q '"has_next":true' "${PAGED_FILE}"

curl -fsS "${WEB_URL}/api/backend/fraud-monitor/dashboard?search=Agency&limit=10" >"${SEARCH_FILE}"
grep -q '"total_matching":1' "${SEARCH_FILE}"
grep -q 'Agency fraud warning fixture' "${SEARCH_FILE}"

RESULT_ID="$(
  python3 - "${DASHBOARD_FILE}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
print(payload["results"][0]["id"])
PY
)"

RESULT_IDS_JSON="$(
  python3 - "${DASHBOARD_FILE}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
print(json.dumps([result["id"] for result in payload["results"]]))
PY
)"

curl -fsS -X PATCH "${WEB_URL}/api/backend/fraud-monitor/review-batches" \
  -H "content-type: application/json" \
  --data-binary "{\"result_ids\":${RESULT_IDS_JSON},\"review_status\":\"not_relevant\"}" \
  >"${BULK_REVIEW_FILE}"
grep -q '"updated_count":2' "${BULK_REVIEW_FILE}"
grep -q '"review_status":"not_relevant"' "${BULK_REVIEW_FILE}"

curl -fsS -X PATCH "${WEB_URL}/api/backend/fraud-monitor/results/${RESULT_ID}" \
  -H "content-type: application/json" \
  --data-binary '{"review_status":"relevant"}' \
  >"${REVIEW_FILE}"
grep -q '"review_status":"relevant"' "${REVIEW_FILE}"

curl -fsS -X POST "${WEB_URL}/api/backend/fraud-monitor/results/${RESULT_ID}/evidence-links" \
  -H "content-type: application/json" \
  --data-binary '{"analyst_note":"Saved during deterministic smoke check."}' \
  >"${EVIDENCE_FILE}"
grep -q '"analyst_note":"Saved during deterministic smoke check."' "${EVIDENCE_FILE}"

EVIDENCE_ID="$(
  python3 - "${EVIDENCE_FILE}" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)
print(payload["id"])
PY
)"

curl -fsS -X PATCH "${WEB_URL}/api/backend/fraud-monitor/evidence-links/${EVIDENCE_ID}" \
  -H "content-type: application/json" \
  --data-binary '{"analyst_note":"Updated during deterministic smoke check."}' \
  >"${NOTE_FILE}"
grep -q '"analyst_note":"Updated during deterministic smoke check."' "${NOTE_FILE}"

curl -fsS "${WEB_URL}/api/backend/fraud-monitor/dashboard" >"${DASHBOARD_FILE}"
grep -q '"evidence_count":1' "${DASHBOARD_FILE}"
grep -q '"relevant_results":1' "${DASHBOARD_FILE}"
grep -q '"saved_as_evidence":true' "${DASHBOARD_FILE}"
grep -q '"evidence_analyst_note":"Updated during deterministic smoke check."' "${DASHBOARD_FILE}"

curl -fsS "${WEB_URL}/api/backend/fraud-monitor/exports/json" >"${JSON_EXPORT_FILE}"
grep -q '"local_only":true' "${JSON_EXPORT_FILE}"
grep -q '"reviewed_result_count":2' "${JSON_EXPORT_FILE}"
grep -q '"source_url":"https://fixture.example' "${JSON_EXPORT_FILE}"
grep -q '"provider":"fixture"' "${JSON_EXPORT_FILE}"
grep -q '"analyst_note":"Updated during deterministic smoke check."' "${JSON_EXPORT_FILE}"

curl -fsS "${WEB_URL}/api/backend/fraud-monitor/exports/markdown" >"${MARKDOWN_EXPORT_FILE}"
grep -q '# Fraud Monitor Export' "${MARKDOWN_EXPORT_FILE}"
grep -q 'Updated during deterministic smoke check.' "${MARKDOWN_EXPORT_FILE}"
grep -q 'analyst review required' "${MARKDOWN_EXPORT_FILE}"
grep -q 'Public results are leads for analyst review' "${MARKDOWN_EXPORT_FILE}"

curl -fsS "${WEB_URL}" >"${WEB_AFTER_FILE}"
grep -q 'Review queue' "${WEB_AFTER_FILE}"
grep -q 'Export Markdown' "${WEB_AFTER_FILE}"
grep -q 'Export JSON' "${WEB_AFTER_FILE}"
grep -q 'Search' "${WEB_AFTER_FILE}"
grep -q 'Sort' "${WEB_AFTER_FILE}"
grep -q 'Select page' "${WEB_AFTER_FILE}"
grep -q 'Provider' "${WEB_AFTER_FILE}"
grep -q 'Evidence' "${WEB_AFTER_FILE}"
grep -q 'Fixture' "${WEB_AFTER_FILE}"
grep -q 'Config ok' "${WEB_AFTER_FILE}"

echo "API health: $(cat "${API_HEALTH_FILE}")"
echo "DB health: $(cat "${DB_HEALTH_FILE}")"
echo "Web dashboard: Fraud Monitor rendered"
echo "Fraud monitor smoke: fixture run, search, pagination, bulk review, evidence note edit, exports, filters, and schedule verified without live provider calls"
