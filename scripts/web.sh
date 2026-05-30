#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NEXT_ENV_FILE="${ROOT_DIR}/apps/web/next-env.d.ts"
NEXT_ENV_BACKUP="$(mktemp)"
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

  wait "${WEB_PID}" 2>/dev/null || true

  if [[ -f "${NEXT_ENV_BACKUP}" ]]; then
    cp "${NEXT_ENV_BACKUP}" "${NEXT_ENV_FILE}"
    rm -f "${NEXT_ENV_BACKUP}"
  fi

  exit "${status}"
}

trap cleanup EXIT INT TERM

cp "${NEXT_ENV_FILE}" "${NEXT_ENV_BACKUP}"
rm -rf "${ROOT_DIR}/apps/web/.next/dev"

cd "${ROOT_DIR}/apps/web"
API_BASE_URL=http://127.0.0.1:8000 npm run dev &
WEB_PID=$!

wait "${WEB_PID}"
