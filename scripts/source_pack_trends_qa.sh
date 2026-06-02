#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_DIR="${ROOT_DIR}/apps/api"
QA_ROOT="${OSINT_CASEOPS_SOURCE_PACK_QA_DIR:-$(mktemp -d "${TMPDIR:-/tmp}/osint-source-pack-qa.XXXXXX")}"
BASE_PORT="${OSINT_CASEOPS_SOURCE_PACK_QA_PORT:-8010}"
CLEANED_UP=0
SERVER_PID=""

cleanup() {
  local status=$?
  if [[ "${CLEANED_UP}" -eq 1 ]]; then
    exit "${status}"
  fi
  CLEANED_UP=1
  if [[ -n "${SERVER_PID}" ]]; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" >/dev/null 2>&1 || true
  fi
  if [[ -z "${OSINT_CASEOPS_SOURCE_PACK_QA_DIR:-}" ]]; then
    rm -rf "${QA_ROOT}"
  fi
  exit "${status}"
}

trap cleanup EXIT INT TERM

json_value() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

value = payload
for part in sys.argv[2].split("."):
    if part.isdigit():
        value = value[int(part)]
    else:
        value = value[part]
print(value)
PY
}

json_assert() {
  python3 - "$1" "$2" <<'PY'
import json
import sys

with open(sys.argv[1], encoding="utf-8") as handle:
    payload = json.load(handle)

expression = sys.argv[2]
if not eval(expression, {"payload": payload, "any": any, "all": all, "len": len}):
    raise SystemExit(f"JSON assertion failed: {expression}")
PY
}

wait_for_api() {
  local url="$1"
  local health_file="$2"
  for _ in $(seq 1 45); do
    if curl -fsS "${url}/health" >"${health_file}" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

start_api() {
  local mode="$1"
  local providers="$2"
  local fixture_enabled="$3"
  local port="$4"
  local data_dir="${QA_ROOT}/${mode}-data"
  local log_file="${QA_ROOT}/${mode}-api.log"

  mkdir -p "${data_dir}"
  (
    cd "${API_DIR}"
    OSINT_CASEOPS_DATA_DIR="${data_dir}" \
    OSINT_CASEOPS_ENABLE_FIXTURE_PROVIDER="${fixture_enabled}" \
    OSINT_CASEOPS_FRAUD_MONITOR_PROVIDERS="${providers}" \
    uv run uvicorn app.main:app --host 127.0.0.1 --port "${port}" >"${log_file}" 2>&1
  ) &
  SERVER_PID=$!
}

stop_api() {
  if [[ -n "${SERVER_PID}" ]]; then
    kill "${SERVER_PID}" >/dev/null 2>&1 || true
    wait "${SERVER_PID}" >/dev/null 2>&1 || true
    SERVER_PID=""
  fi
}

run_mode() {
  local mode="$1"
  local providers="$2"
  local fixture_enabled="$3"
  local port="$4"
  local require_result="$5"
  local expected_provider="$6"
  local url="http://127.0.0.1:${port}"
  local mode_dir="${QA_ROOT}/${mode}"
  local health_file="${mode_dir}/health.json"
  local db_file="${mode_dir}/db-health.json"
  local config_file="${mode_dir}/configuration.json"
  local job_file="${mode_dir}/job.json"
  local dashboard_file="${mode_dir}/dashboard.json"
  local review_file="${mode_dir}/review.json"
  local evidence_file="${mode_dir}/evidence.json"
  local evidence_update_file="${mode_dir}/evidence-update.json"
  local export_json_file="${mode_dir}/export.json"
  local export_markdown_file="${mode_dir}/export.md"

  mkdir -p "${mode_dir}"
  echo "== ${mode}: providers=${providers} =="
  start_api "${mode}" "${providers}" "${fixture_enabled}" "${port}"

  if ! wait_for_api "${url}" "${health_file}"; then
    echo "API did not become ready for ${mode}. Log follows:" >&2
    cat "${QA_ROOT}/${mode}-api.log" >&2
    return 1
  fi

  curl -fsS "${url}/health/db" >"${db_file}"
  curl -fsS "${url}/fraud-monitor/configuration/validation" >"${config_file}"
  curl -fsS -X POST "${url}/fraud-monitor/jobs" >"${job_file}"
  curl -fsS "${url}/fraud-monitor/dashboard" >"${dashboard_file}"

  json_assert "${health_file}" "payload['status'] == 'ok'"
  json_assert "${db_file}" "payload['status'] == 'ok'"
  json_assert "${config_file}" "payload['provider_count'] >= 1"
  json_assert "${dashboard_file}" "payload['trend_overview']['provider_health']"
  json_assert "${dashboard_file}" "any(provider['name'] == '${expected_provider}' or provider['provider_id'] == '${expected_provider}' for provider in payload['providers'])"

  local result_count
  result_count="$(json_value "${dashboard_file}" "total_results")"
  if [[ "${require_result}" == "1" && "${result_count}" -lt 1 ]]; then
    echo "${mode} expected at least one stored result but found ${result_count}." >&2
    cat "${job_file}" >&2
    return 1
  fi

  if [[ "${result_count}" -ge 1 ]]; then
    local result_id evidence_id
    result_id="$(json_value "${dashboard_file}" "results.0.id")"
    curl -fsS -X PATCH "${url}/fraud-monitor/results/${result_id}" \
      -H "content-type: application/json" \
      --data-binary '{"review_status":"relevant"}' \
      >"${review_file}"
    curl -fsS -X POST "${url}/fraud-monitor/results/${result_id}/evidence-links" \
      -H "content-type: application/json" \
      --data-binary "{\"analyst_note\":\"Source-pack QA note for ${mode}.\"}" \
      >"${evidence_file}"
    evidence_id="$(json_value "${evidence_file}" "id")"
    curl -fsS -X PATCH "${url}/fraud-monitor/evidence-links/${evidence_id}" \
      -H "content-type: application/json" \
      --data-binary "{\"analyst_note\":\"Updated source-pack QA note for ${mode}.\"}" \
      >"${evidence_update_file}"

    curl -fsS "${url}/fraud-monitor/dashboard" >"${dashboard_file}"
    json_assert "${dashboard_file}" "payload['relevant_results'] >= 1"
    json_assert "${dashboard_file}" "payload['evidence_count'] >= 1"
    json_assert "${dashboard_file}" "payload['results'][0]['fraud_category']"
    json_assert "${dashboard_file}" "payload['trend_overview']['top_categories_this_week'] or payload['trend_overview']['official_source_alerts'] or payload['trend_overview']['emerging_keywords']"
  fi

  curl -fsS "${url}/fraud-monitor/exports/json" >"${export_json_file}"
  curl -fsS "${url}/fraud-monitor/exports/markdown" >"${export_markdown_file}"
  grep -q '"local_only":true' "${export_json_file}"
  grep -q '# Fraud Monitor Export' "${export_markdown_file}"
  if [[ "${result_count}" -ge 1 ]]; then
    grep -q "Updated source-pack QA note for ${mode}" "${export_markdown_file}"
  fi

  echo "${mode}: health, provider status, run, review/evidence when available, trends, and exports verified."
  stop_api
}

mkdir -p "${QA_ROOT}"
echo "Source-pack/trends QA data: ${QA_ROOT}"

run_mode "fixture" "fixture" "1" "${BASE_PORT}" "1" "fixture"
run_mode "no-key" "gdelt_doc,google_news_rss,hn_algolia" "0" "$((BASE_PORT + 1))" "0" "gdelt_doc"
run_mode "official-doj" "doj_news" "0" "$((BASE_PORT + 2))" "1" "doj_news"

echo "Source-pack/trends operator QA complete."
