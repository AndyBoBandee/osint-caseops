#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
API_PID=""
WEB_PID=""
CLEANED_UP=0

cleanup() {
  local status=$?
  if [[ "${CLEANED_UP}" -eq 1 ]]; then
    exit "${status}"
  fi
  CLEANED_UP=1

  if [[ -n "${WEB_PID}" ]] && kill -0 "${WEB_PID}" 2>/dev/null; then
    kill "${WEB_PID}" 2>/dev/null || true
  fi

  if [[ -n "${API_PID}" ]] && kill -0 "${API_PID}" 2>/dev/null; then
    kill "${API_PID}" 2>/dev/null || true
  fi

  wait "${WEB_PID}" 2>/dev/null || true
  wait "${API_PID}" 2>/dev/null || true
  exit "${status}"
}

trap cleanup EXIT INT TERM

echo "Starting API at http://127.0.0.1:8000"
(
  cd "${ROOT_DIR}/apps/api"
  uv run uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
) &
API_PID=$!

echo "Starting web at http://127.0.0.1:3000"
"${ROOT_DIR}/scripts/web.sh" &
WEB_PID=$!

echo "Press Ctrl+C to stop both services."
while kill -0 "${API_PID}" 2>/dev/null && kill -0 "${WEB_PID}" 2>/dev/null; do
  sleep 1
done

EXIT_STATUS=0

if ! kill -0 "${API_PID}" 2>/dev/null; then
  wait "${API_PID}" 2>/dev/null || EXIT_STATUS=$?
fi

if ! kill -0 "${WEB_PID}" 2>/dev/null; then
  wait "${WEB_PID}" 2>/dev/null || {
    WEB_STATUS=$?
    if [[ "${EXIT_STATUS}" -eq 0 ]]; then
      EXIT_STATUS="${WEB_STATUS}"
    fi
  }
fi

exit "${EXIT_STATUS}"
