#!/usr/bin/env bash
set -euo pipefail

PYTHON_BIN="${PYTHON:-python3}"
TEMPORAL_CONTAINER="${TEMPORAL_CONTAINER:-agora-temporal}"
PRECHECK_SCRIPT="scripts/preflight_temporal.sh"
LOG_FILE="$(mktemp -t agora-cmd12.XXXXXX.log)"
RETRIED=0

cleanup() {
  rm -f "${LOG_FILE}"
}
trap cleanup EXIT

if [[ ! -x "${PRECHECK_SCRIPT}" ]]; then
  chmod +x "${PRECHECK_SCRIPT}"
fi

echo "Running Temporal preflight before integration tests..."
POLL_INTERVAL_SECONDS=3 MAX_WAIT_SECONDS=150 ALLOW_RESTART_ON_EXIT=1 \
  "${PRECHECK_SCRIPT}" "${TEMPORAL_CONTAINER}"

run_integration() {
  set +e
  make PYTHON="${PYTHON_BIN}" test-integration 2>&1 | tee "${LOG_FILE}"
  status=${PIPESTATUS[0]}
  set -e
  return "${status}"
}

if run_integration; then
  echo "Guarded integration path passed without retry."
  exit 0
fi

if grep -Eqi "ConnectionRefusedError|connection refused|temporal.*unavailable|failed to connect|ConnectError" "${LOG_FILE}"; then
  echo "Detected transient Temporal startup failure signature."
  echo "Restarting Temporal and retrying integration tests once..."
  docker restart "${TEMPORAL_CONTAINER}" >/dev/null
  POLL_INTERVAL_SECONDS=3 MAX_WAIT_SECONDS=150 ALLOW_RESTART_ON_EXIT=0 \
    "${PRECHECK_SCRIPT}" "${TEMPORAL_CONTAINER}"
  RETRIED=1
  run_integration
fi

if [[ "${RETRIED}" -eq 1 ]]; then
  echo "Guarded integration path passed after one Temporal retry."
else
  echo "Integration failed without transient Temporal startup signature; not retrying." >&2
  exit 1
fi
