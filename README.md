# ctrl

Execution control plane for AI agents with MCP tool interception, policy enforcement, and an auditable ledger. ctrl sits between a LangChain agent and its MCP servers, evaluates intent against policies + risk, and records every decision in SQLite.

Status: early v0; interfaces may change quickly.

---

## What it does
- LangChain-first wrapper (`CtrlMCP`) that swaps in for `MultiServerMCPClient`
- Policy engine (allow/deny/pending) with optional approval gating driven by risk
- Risk scoring pipeline (rules + expressions, server/tool/env/args aware)
- SQLite-backed audit tables (`requests`, `decisions`, `events`) with hashes of tool args
- CLI: config validation, policy lint/explain/test, approvals API server

---

## Requirements
- Python 3.11+
- Poetry
- SQLite (bundled with Python)

---

## Install
```bash
git clone <repo-url>
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

Tool calls now flow through: log intent -> score risk -> decide policy -> enforce -> forward to MCP server. Deny/pending raise `PermissionError` before execution.

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
- Policies that resolve to `pending` are blocked until approved.
- Start the lightweight API:
```bash
poetry run ctrl approvals-serve --host 127.0.0.1 --port 8788
```
- Endpoints:
  - `GET /pending` — list pending requests
  - `GET /status/{request_id}` — request + last decision
  - `POST /approve/{request_id}` — mark approved and execute the tool via MCP
  - `POST /deny/{request_id}` — mark denied
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
