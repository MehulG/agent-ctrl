# Publish Market Report (E2E Demo)

This demo runs a LangChain agent that fetches crypto market data from CoinGecko, generates HTML, and publishes it via EdgeOne. All tool calls are intercepted by ctrl and recorded in the SQLite ledger.

## Prerequisites
- Python 3.11+
- Poetry
- `GOOGLE_API_KEY` for the Gemini model
- MCP servers for CoinGecko + EdgeOne configured in `demos/e2e_publish_market_report/configs/servers.yaml`

## Steps
1) Install dependencies (from repo root):
```bash
poetry install
```

2) Run the demo (validates config and initializes the DB automatically):
```bash
GOOGLE_API_KEY=<key> poetry run demos/e2e_publish_market_report/run.sh
```

3) (Optional) Start the approvals API if you see a pending request ID:
```bash
poetry run ctrl approvals-serve --host 127.0.0.1 --port 8788
```

The agent prints the EdgeOne URL + insights when the publish executes immediately. If a request is pending, approve it via the API or dashboard; the approvals service will execute the publish, and you can fetch the URL from the dashboard or `GET /status/<id>`.

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
- If EdgeOne tools are missing or publish fails, the agent will output `EDGEONE_TOOL_MISSING` and stop.
- Check `ctrl.db` for requests/events if the run halts unexpectedly.
- The demo policy denies when risk mode is `danger` and requires approval when `review` (EdgeOne publish defaults to `review`).
