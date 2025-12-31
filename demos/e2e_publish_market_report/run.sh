#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"

cd "${ROOT_DIR}"

if [[ -z "${GOOGLE_API_KEY:-}" ]]; then
  echo "GOOGLE_API_KEY is required for the Gemini model" >&2
  exit 1
fi

echo "Validating configs..."
poetry run ctrl validate-config \
  --servers "${SCRIPT_DIR}/configs/servers.yaml" \
  --policy "${SCRIPT_DIR}/configs/policy.yaml" \
  --db ctrl.db

echo "Running LangChain agent..."
poetry run python "${SCRIPT_DIR}/agent.py"

echo
echo "Ledger path: ${ROOT_DIR}/ctrl.db"
echo "If you got a pending ID:"
echo "  1) poetry run ctrl approvals-serve --host 127.0.0.1 --port 8788"
echo "  2) curl -X POST http://127.0.0.1:8788/approve/<id>"
echo "  3) curl http://127.0.0.1:8788/status/<id>  # fetch publish result"
