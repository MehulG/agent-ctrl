# ctrl

Execution control plane for AI agents with MCP tool interception, policy enforcement, and an auditable ledger.

One-liner: drop-in `CtrlMCP` wrapper for LangChain that risk-scores every MCP tool call, applies policy (allow/deny/pending), and records the full audit trail in SQLite.

Status: early v0; APIs may change quickly—treat the demos as the source of truth.

---

## 5-minute demo (publish a market report)
Run the end-to-end demo that fetches crypto data and publishes a static page through EdgeOne. Requires Python 3.11+, Poetry, and `GOOGLE_API_KEY` for the Gemini model.

```bash
git clone https://github.com/MehulG/agent-ctrl
cd ctrl
poetry install

# validate configs + init SQLite ledger
poetry run ctrl validate-config \
  --servers demos/e2e_publish_market_report/configs/servers.yaml \
  --policy demos/e2e_publish_market_report/configs/policy.yaml \
  --db ctrl.db

# run the LangChain agent (prints a pending ID or a URL + insights)
GOOGLE_API_KEY=<key> ./demos/e2e_publish_market_report/run.sh
```

The agent calls CoinGecko first, generates HTML, and attempts to publish via EdgeOne. If policy returns `pending`, you will see a request ID (the agent exits after printing it); start the approvals API, approve the request so the approvals service executes the publish, then fetch the result via the dashboard or `GET /status/<id>`. More context: `docs/quickstart.md`.

If you see a pending ID:
Run approvals service from the repo root so it shares the same configs and `ctrl.db`:
```bash
poetry run ctrl approvals-serve --host 127.0.0.1 --port 8788
curl -X POST http://127.0.0.1:8788/approve/<id>
curl http://127.0.0.1:8788/status/<id>
# or open the dashboard UI (start from dashboard/, default http://localhost:5173)
```

### Docker (agent + approvals + dashboard)
Prefer containers? Use the bundled compose in `demos/e2e_publish_market_report/`:
1) Copy `.env.example` to `.env` in that folder and set values (at minimum `GOOGLE_API_KEY`; set `NEXT_PUBLIC_CTRL_API_BASE` to a host/IP your browser can reach).
2) From repo root, start long-running services:
```bash
docker compose --env-file demos/e2e_publish_market_report/.env -f demos/e2e_publish_market_report/docker-compose.yml up -d approvals dashboard --build
```
3) Run the agent as a one-off (re-run anytime):
```bash
docker compose --env-file demos/e2e_publish_market_report/.env -f demos/e2e_publish_market_report/docker-compose.yml run --rm agent
```
Ports by default: approvals API `http://localhost:8788`, dashboard `http://localhost:3000`. The shared ledger lives in the `ctrl-data` volume at `/data/ctrl.db`.

---

## What it does
- LangChain-first wrapper (`CtrlMCP`) that swaps in for `MultiServerMCPClient`
- Policy engine (allow/deny/pending) with optional approval gating driven by risk
- Risk scoring pipeline (rules + expressions, server/tool/env/args aware)
- SQLite-backed audit tables (`requests`, `decisions`, `events`) with hashes of tool args
- CLI: config validation, policy lint/explain/test, approvals API server

---

## Architecture
```
LangChain agent
   |
   v
CtrlMCP wrapper
   |  log intent -> score risk -> apply policy
   v
SQLite ledger (requests/decisions/events)
   |
   +--> Approvals API + dashboard (for pending)
   |
   v
MCP servers (CoinGecko, EdgeOne, ...)
```

---

## Requirements
- Python 3.11+
- Poetry
- SQLite (bundled with Python)

---

## Install
```bash
git clone https://github.com/MehulG/agent-ctrl
cd ctrl
poetry install

# verify
poetry run ctrl version
```

---

## Quickstart: LangChain + MCP
1) Define servers and policies.
`configs/servers.yaml`
```yaml
servers:
  - name: context7
    transport: http
    base_url: "https://mcp.context7.com/mcp"
```

`configs/policy.yaml`
```yaml
policies:
  - id: context7-approval
    match: { server: "context7", tool: "*", env: "*" }
    effect: allow
    reason: "Context7 allowed but gated by risk"
    require_approval_if: "risk.mode in ['review','danger']"

  - id: allow-default
    match: { server: "*", tool: "*", env: "*" }
    effect: allow
    reason: "Default allow"
```

`configs/risk.yaml`
```yaml
risk:
  mode: modes
  modes: { safe: {score: 10}, review: {score: 50}, danger: {score: 90} }
  rules:
    - name: context7-safe
      when: { server: "context7", tool: "*" }
      set_mode: safe
      reason: "Read-only documentation"
  set_mode_by_score:
    danger: "score >= 70"
    review: "score >= 40"
    safe: "score < 40"
```

2) Validate config and initialize the database.
```bash
poetry run ctrl validate-config --servers configs/servers.yaml --policy configs/policy.yaml --db ctrl.db
# risk.yaml is loaded at runtime (no CLI validator yet)
```

3) Wrap your LangChain MCP client.
```python
from ctrl.langchain.client import CtrlMCP

mcp = CtrlMCP(
    servers="configs/servers.yaml",
    policy="configs/policy.yaml",
    risk="configs/risk.yaml",
    db_path="ctrl.db",
    default_env="dev",          # overridable via request headers (x-ctrl-env)
    tool_name_prefix=False,      # same semantics as MultiServerMCPClient
)

tools = await mcp.get_tools()   # returns LangChain tools with interception attached
```

Tool calls now flow through: log intent -> score risk -> decide policy -> enforce -> forward to MCP server. `deny` raises `PermissionError`; `pending` is an expected outcome that either returns a pending payload (when `return_on_pending=True`) or raises `PermissionError` with the request ID. No tool runs until approval is issued via the approvals service.
Recommendation: use `allow + require_approval_if` for conditional gating and reserve `effect: pending` for always-gated tools.

---

## Policies
- Evaluated in order (first match wins).
- Match fields support shell-style wildcards: `server`, `tool`, `env`.
- Effects: `allow`, `deny`, `pending`.
- `require_approval_if` overrides an allow to pending when the expression evaluates truthy; it is evaluated with `risk` context (`risk.mode`, `risk.score`, `risk.reasons`, `risk.rules`).

Example rule:
```yaml
- id: deny-prod-delete
  match: { server: "*", tool: "*delete*", env: "prod" }
  effect: deny
  reason: "Deletes in prod blocked"
```

Use `ctrl policy explain` to see which policy would match a given server/tool/env.

---

## Risk scoring
- Config-driven in `configs/risk.yaml` with named modes (safe/review/danger) and baseline scores.
- Rules can set a mode, escalate one level, or compute scores via expressions (see `ctrl/risk/expr.py` for the sandboxed evaluator).
- `set_mode_by_score` maps final numeric scores back to modes to keep them aligned.
- Risk results are attached to every request row and emitted as an event.

---

## Approvals (pending -> human)
- Requests that resolve to `pending` are blocked until approved.
- Start the lightweight API:
```bash
poetry run ctrl approvals-serve --host 127.0.0.1 --port 8788
```
- Endpoints:
  - `GET /pending` — list pending requests
  - `GET /status/{request_id}` — request + last decision
  - `POST /approve/{request_id}` — mark approved and execute the tool via MCP
  - `POST /deny/{request_id}` — mark denied
- Approvals service replays the tool call on approval; fetch the result via `GET /status/{request_id}` or the dashboard.
- Uses the same `ctrl.db` ledger; events capture approval decisions and execution results.

---

## Audit trail (SQLite)
- `requests`: intent ledger (server/tool/env/args hash, actor, risk score, status)
- `decisions`: policy outcome + matched policy id and condition
- `events`: append-only timeline (`request.created`, `risk.scored`, `decision.made`, `proxy.*`, `approval.*`)

Inspect with `sqlite3 ctrl.db` or any GUI. Example:
```sql
select id, created_at, server, tool, env, status, risk_score
from requests
order by created_at desc
limit 20;
```

---

## CLI reference
- `ctrl version`
- `ctrl validate-config --servers configs/servers.yaml --policy configs/policy.yaml --db ctrl.db`
- `ctrl policy lint --policy configs/policy.yaml`
- `ctrl policy explain --server <name> --tool <name> [--env dev]`
- `ctrl policy test configs/policy_tests.yaml --policy configs/policy.yaml`
- `ctrl approvals-serve [--host 0.0.0.0] [--port 8788]`

---

## Project layout
```
ctrl/
  cli/                # Typer CLI entrypoints
  approvals/          # FastAPI approval service
  config/             # YAML loading + validation
  db/                 # migrations + ensure_db
  langchain/          # CtrlMCP wrapper and interceptor
  policy/             # policy engine, lint, explain, test
  risk/               # risk engine + expression sandbox
configs/              # example policy/risk/server configs
migrations/           # SQLite schema
```

---

## Development
- Lint: `poetry run ruff check .`
- Tests: `poetry run pytest`
- DB migrations are in `migrations/`; `ensure_db` will apply them automatically at runtime.

PRs and issues are welcome. Keep changes small, validated, and focused on reliability of the control plane.
