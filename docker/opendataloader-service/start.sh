#!/usr/bin/env bash
set -euo pipefail

HYBRID_PORT="${HYBRID_PORT:-5002}"
APP_PORT="${APP_PORT:-9385}"

if [[ "${ENABLE_HYBRID:-false}" == "true" ]]; then
  echo "[start] launching opendataloader-pdf-hybrid on :${HYBRID_PORT}"
  opendataloader-pdf-hybrid --port "${HYBRID_PORT}" &
  HYBRID_PID=$!
  trap "kill ${HYBRID_PID} 2>/dev/null || true" EXIT

  # wait for hybrid server to come up (max 120s; first run downloads models)
  for i in $(seq 1 120); do
    if curl -fsS "http://localhost:${HYBRID_PORT}/health" >/dev/null 2>&1 \
       || curl -fsS "http://localhost:${HYBRID_PORT}/" >/dev/null 2>&1; then
      echo "[start] hybrid server is up"
      break
    fi
    sleep 1
  done
fi

exec uvicorn app:app --host 0.0.0.0 --port "${APP_PORT}"
