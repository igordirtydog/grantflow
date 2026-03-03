#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${ROOT_DIR}"

if command -v docker >/dev/null 2>&1 && docker compose version >/dev/null 2>&1; then
  COMPOSE_CMD=(docker compose)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE_CMD=(docker-compose)
else
  echo "docker compose is not available"
  exit 1
fi

cleanup() {
  "${COMPOSE_CMD[@]}" logs api >/tmp/grantflow-docker-compose-api.log 2>&1 || true
  "${COMPOSE_CMD[@]}" down -v --remove-orphans || true
}
trap cleanup EXIT

"${COMPOSE_CMD[@]}" down -v --remove-orphans || true
"${COMPOSE_CMD[@]}" up -d --build

for _ in $(seq 1 90); do
  if curl -fsS http://127.0.0.1:8000/health >/dev/null; then
    break
  fi
  sleep 2
done
curl -fsS http://127.0.0.1:8000/health >/dev/null

generate_payload='{"donor_id":"usaid","input_context":{"project":"Docker Smoke Proposal","country":"Kenya"},"llm_mode":false,"hitl_enabled":false}'
generate_response="$(curl -fsS -X POST http://127.0.0.1:8000/generate -H 'Content-Type: application/json' -d "${generate_payload}")"
job_id="$(python3 -c 'import json,sys; print(json.loads(sys.stdin.read())["job_id"])' <<<"${generate_response}")"

terminal_status=""
for _ in $(seq 1 90); do
  status_payload="$(curl -fsS "http://127.0.0.1:8000/status/${job_id}")"
  terminal_status="$(python3 -c 'import json,sys; print((json.loads(sys.stdin.read()).get("status") or "").strip())' <<<"${status_payload}")"
  if [[ "${terminal_status}" == "done" ]]; then
    echo "docker-compose smoke: job ${job_id} completed"
    exit 0
  fi
  if [[ "${terminal_status}" == "error" || "${terminal_status}" == "canceled" ]]; then
    echo "docker-compose smoke: job ${job_id} terminal status=${terminal_status}"
    exit 1
  fi
  sleep 2
done

echo "docker-compose smoke: timeout waiting for terminal success (last_status=${terminal_status:-unknown})"
exit 1
