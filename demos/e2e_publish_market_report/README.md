# Publish Market Report (E2E Demo)

This demo runs a LangChain agent that fetches crypto market data from
CoinGecko, generates HTML, and publishes it via EdgeOne. All tool calls
are intercepted by ctrl and recorded in the SQLite ledger.

## Prerequisites
- Python 3.11+
- Poetry
- MCP servers for CoinGecko + EdgeOne configured in `demos/e2e_publish_market_report/configs/servers.yaml`

## Steps
1) Install dependencies (from repo root):
```bash
poetry install
```

2) Validate config and initialize the database:
```bash
poetry run ctrl validate-config \
  --servers demos/e2e_publish_market_report/configs/servers.yaml \
  --policy demos/e2e_publish_market_report/configs/policy.yaml \
  --db ctrl.db
```

3) (Optional) Start the approvals API:
```bash
poetry run ctrl approvals-serve --host 127.0.0.1 --port 8788
```

4) Run the demo agent:
```bash
poetry run python demos/e2e_publish_market_report/agent.py
```

The agent prints the EdgeOne URL + insights on success.

## Dashboard (Optional)
From `dashboard/`, start the UI and point it at the approvals API:
```bash
cd dashboard
yarn
yarn dev
```

Then open the dashboard and use:
- API base URL: `http://127.0.0.1:8788`
- Database path: `ctrl.db`

With the approvals API and dashboard running, you can review tool call parameters and approve or deny the publication request.

## Troubleshooting
- If EdgeOne tools are missing or publish fails, the agent will output
  `EDGEONE_TOOL_MISSING` and stop.
- Check `ctrl.db` for requests/events if the run halts unexpectedly.
