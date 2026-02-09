#!/usr/bin/env bash
set -euo pipefail

TEMPORAL_CONTAINER="${TEMPORAL_CONTAINER:-agora-temporal}"
MAX_WAIT_SECONDS="${MAX_WAIT_SECONDS:-120}"
POLL_INTERVAL_SECONDS="${POLL_INTERVAL_SECONDS:-3}"
ALLOW_RESTART_ON_EXIT="${ALLOW_RESTART_ON_EXIT:-1}"

if [[ $# -gt 0 ]]; then
  TEMPORAL_CONTAINER="$1"
fi

if ! command -v docker >/dev/null 2>&1; then
  echo "ERROR: docker is required for Temporal preflight." >&2
  exit 2
fi

echo "Temporal preflight: container=${TEMPORAL_CONTAINER} max_wait=${MAX_WAIT_SECONDS}s poll=${POLL_INTERVAL_SECONDS}s"

deadline=$((SECONDS + MAX_WAIT_SECONDS))
restart_attempted=0
last_state="<unknown>"
last_health="<unknown>"

while (( SECONDS < deadline )); do
  inspect="$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "${TEMPORAL_CONTAINER}" 2>/dev/null || true)"
  if [[ -z "${inspect}" ]]; then
    echo "Temporal container '${TEMPORAL_CONTAINER}' not visible yet; waiting..."
    sleep "${POLL_INTERVAL_SECONDS}"
    continue
  fi

  state="${inspect%% *}"
  health="${inspect#* }"
  last_state="${state}"
  last_health="${health}"

  echo "Temporal state=${state} health=${health}"

  if [[ "${state}" == "running" && "${health}" == "healthy" ]]; then
    echo "Temporal preflight OK."
    exit 0
  fi

  if [[ "${ALLOW_RESTART_ON_EXIT}" == "1" && "${restart_attempted}" -eq 0 && ( "${state}" == "exited" || "${state}" == "dead" ) ]]; then
    echo "Temporal container is ${state}; attempting one restart..."
    docker start "${TEMPORAL_CONTAINER}" >/dev/null
    restart_attempted=1
  fi

  sleep "${POLL_INTERVAL_SECONDS}"
done

echo "ERROR: Temporal preflight timed out (${MAX_WAIT_SECONDS}s)." >&2
echo "Last observed state=${last_state} health=${last_health}" >&2
docker ps --filter "name=${TEMPORAL_CONTAINER}" --format 'table {{.Names}}\t{{.Status}}' || true
docker logs --tail 80 "${TEMPORAL_CONTAINER}" || true
exit 1
