#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${ROOT_DIR}"

ENV_FILE="${SCRIPT_DIR}/.env"
if [[ -f "${ENV_FILE}" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "${ENV_FILE}"
  set +a
fi

if [[ -z "${GOOGLE_API_KEY:-}" ]]; then
  echo "GOOGLE_API_KEY is required for the Gemini model" >&2
  exit 1
fi

DB_PATH="${CTRL_DB_PATH:-ctrl.db}"
SERVERS_PATH="${CTRL_SERVERS_PATH:-${SCRIPT_DIR}/configs/servers.yaml}"
POLICY_PATH="${CTRL_POLICY_PATH:-${SCRIPT_DIR}/configs/policy.yaml}"
export CTRL_DB_PATH="${DB_PATH}"
export CTRL_SERVERS_PATH="${SERVERS_PATH}"
export CTRL_POLICY_PATH="${POLICY_PATH}"
export CTRL_RISK_PATH="${CTRL_RISK_PATH:-${SCRIPT_DIR}/configs/risk.yaml}"

echo "Validating configs..."
poetry run ctrl validate-config \
  --servers "${SERVERS_PATH}" \
  --policy "${POLICY_PATH}" \
  --db "${DB_PATH}"

echo "Running LangChain agent..."
poetry run python "${SCRIPT_DIR}/agent.py"

echo
echo "Ledger path: ${DB_PATH}"
echo "If you got a pending ID:"
echo "  1) poetry run ctrl approvals-serve --host 127.0.0.1 --port 8788"
echo "  2) curl -X POST http://127.0.0.1:8788/approve/<id>"
echo "  3) curl http://127.0.0.1:8788/status/<id>  # fetch publish result"
