# Quickstart: publish a market report

This guide walks through the end-to-end demo that fetches crypto market data, generates HTML, and publishes a static page. All MCP tool calls flow through ctrl for risk and policy checks.

## Prerequisites
- Python 3.11+, Poetry, SQLite (bundled)
- `GOOGLE_API_KEY` for the Gemini model used by the agent
- Outbound HTTPS to the demo MCP servers:
  - CoinGecko: `https://mcp.api.coingecko.com/mcp`
  - EdgeOne: `https://mcp-on-edge.edgeone.site/mcp-server`

## Files involved
- `demos/e2e_publish_market_report/agent.py` — LangChain agent wired to CtrlMCP
- `demos/e2e_publish_market_report/configs/servers.yaml` — MCP endpoints
- `demos/e2e_publish_market_report/configs/policy.yaml` — allow + approval rules
- `demos/e2e_publish_market_report/configs/risk.yaml` — risk modes and rules
- `ctrl.db` — SQLite ledger created on first run

## Run the demo
From the repo root:
```bash
poetry install

poetry run ctrl validate-config \
  --servers demos/e2e_publish_market_report/configs/servers.yaml \
  --policy demos/e2e_publish_market_report/configs/policy.yaml \
  --db ctrl.db
# risk.yaml is loaded by the agent at runtime (no separate CLI validator yet)

# executes the LangChain agent; prints a URL and insights or a pending ID
GOOGLE_API_KEY=<key> poetry run demos/e2e_publish_market_report/run.sh
```

What happens:
- CoinGecko tool is called first to fetch the top 10 coins.
- The LLM builds HTML with a table (no scripts allowed).
- EdgeOne tool attempts to publish; policy may return `pending` based on risk.

## Handle pending approvals
Start the approvals API if you see a pending request ID (the agent exits after printing it):
```bash
poetry run ctrl approvals-serve --host 127.0.0.1 --port 8788
curl -X POST http://127.0.0.1:8788/approve/<request_id>
```
After approval, the approvals service executes the tool. Fetch the deployed URL from the dashboard or `GET /status/<request_id>`.

## Inspect the ledger
All stages are recorded in SQLite:
```bash
sqlite3 ctrl.db "select id, server, tool, env, status, risk_mode, risk_score from requests order by created_at desc limit 10;"
```

## Demo policy + risk behavior
- Risk rules mark CoinGecko as `safe`, EdgeOne as `review`, and any HTML containing `<script` as `danger`.
- Policy allows all tools but:
  - denies when `risk.mode == 'danger'`
  - requires approval when `risk.mode == 'review'`

## Next steps
- Integrate with your own LangChain agent: `docs/integrations/langchain.md`
- Learn the policy model and ledger schema: `docs/concepts.md`
