
# ctrl

**Execution control plane for AI agents.**

Ctrl sits between *agent intent* and *real-world actions*.  
Agents can *decide* what to do. Ctrl decides what’s *allowed to happen*.

It intercepts tool calls, risk-scores them, enforces policy (allow / deny / approve),
and executes only what’s authorized — with a full, auditable ledger.

**One-liner:** a drop-in `CtrlMCP` wrapper for LangChain that turns agent actions into
**governed execution**.

**Status:** early v0; APIs may change quickly — treat demos as the source of truth.

---

## Why Ctrl exists

AI agents are moving from **reading and drafting** to **acting**:
sending emails, issuing refunds, publishing content, changing production systems.

The moment agents take real actions, intelligence stops being the bottleneck —
**authority, safety, and auditability** do.

Today, teams solve this with ad-hoc allowlists, brittle checks, and manual approvals.
That doesn’t scale, and it breaks the moment agents run faster than humans.

**Ctrl is the missing layer:**
a runtime that decides *whether* an agent action should happen,
*under what constraints*, and *with what proof*.

Think of Ctrl as an **action gateway**:
agents propose actions, Ctrl authorizes and executes them safely.

---

## Demo

https://github.com/user-attachments/assets/495c542f-b222-4f3f-ad90-6b6c82e2325a

---

## 5-minute demo (publish a market report)

Run an end-to-end demo where an agent fetches crypto data and attempts to publish
a static page via EdgeOne.

The publish action is **intercepted**, **risk-scored**, **paused for approval**, and
**replayed safely** after approval.

```bash
git clone https://github.com/MehulG/agent-ctrl
cd ctrl
poetry install

# validate configs + init SQLite ledger
poetry run ctrl validate-config \
  --servers demos/e2e_publish_market_report/configs/servers.yaml \
  --policy demos/e2e_publish_market_report/configs/policy.yaml \
  --db ctrl.db

# run the LangChain agent
GOOGLE_API_KEY=<key> ./demos/e2e_publish_market_report/run.sh
````

If policy returns `pending`, the agent currently exits after printing a request ID.
This is intentional: *nothing runs until approval is recorded*.

Start the approvals API (same configs + shared `ctrl.db`):

```bash
poetry run ctrl approvals-serve --host 127.0.0.1 --port 8788
curl -X POST http://127.0.0.1:8788/approve/<id>
curl http://127.0.0.1:8788/status/<id>
# or open the dashboard UI (default http://localhost:3000)
```

Start the dashboard UI locally:

```bash
cd dashboard
yarn dev --hostname 0.0.0.0 --port 3000
```

Approvals API: http://localhost:8788  
Dashboard UI: http://localhost:3000

---

## Docker (agent + approvals + dashboard)

Prefer containers? Use the bundled compose in
`demos/e2e_publish_market_report/`.

1. Copy `.env.example` → `.env` and set values
2. Start long-running services:

```bash
docker compose --env-file demos/e2e_publish_market_report/.env \
  -f demos/e2e_publish_market_report/docker-compose.yml \
  up -d approvals dashboard --build
```

Approvals API: http://localhost:8788  
Dashboard UI: http://localhost:3000

3. Run the agent:

```bash
docker compose --env-file demos/e2e_publish_market_report/.env \
  -f demos/e2e_publish_market_report/docker-compose.yml \
  run --rm agent
```

---

## What Ctrl does today

* LangChain-first wrapper (`CtrlMCP`) for MCP tool interception
* Policy engine: `allow`, `deny`, or `pending`
* Risk scoring pipeline (rules + expressions)
* SQLite-backed intent and decision ledger
* Lightweight approvals API + dashboard
* CLI for config validation, policy linting, explain, and tests

---

## What Ctrl is evolving into

**A general-purpose action gateway for AI agents.**

The long-term goal is not approvals UI —
it’s making autonomous execution *safe by default*:

* **Delegated authority** instead of shared credentials
* **Budgets, limits, and constraints** instead of blanket access
* **Auto-approval for low risk**, escalation only for edge cases
* **Replay-safe execution** with durable audit trails

As agents begin handling customer communications and financial actions,
Ctrl becomes the place where organizations decide:

> *Which actions can run automatically — and which must never run unchecked.*

---

## Architecture

```
LangChain agent
   |
   v
CtrlMCP wrapper
   |  log intent → score risk → apply policy
   v
SQLite ledger (requests / decisions / events)
   |
   +--> Approvals API + dashboard (for pending)
   |
   v
MCP servers (CoinGecko, EdgeOne, ...)
```

---

## Requirements

* Python 3.11+
* Poetry
* SQLite (bundled with Python)

---

## Install

```bash
git clone https://github.com/MehulG/agent-ctrl
cd ctrl
poetry install
poetry run ctrl version
```

---

## Quickstart: LangChain + MCP

### 1) Define servers and policies

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
    require_approval_if: "risk.mode in ['review','danger']"

  - id: allow-default
    match: { server: "*", tool: "*", env: "*" }
    effect: allow
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
```

### 2) Initialize the database

```bash
poetry run ctrl validate-config \
  --servers configs/servers.yaml \
  --policy configs/policy.yaml \
  --db ctrl.db
```

### 3) Wrap your MCP client

```python
from ctrl.langchain.client import CtrlMCP

mcp = CtrlMCP(
    servers="configs/servers.yaml",
    policy="configs/policy.yaml",
    risk="configs/risk.yaml",
    db_path="ctrl.db",
)

tools = await mcp.get_tools()
```

Tool calls now flow through:
**log intent → score risk → decide policy → enforce → execute**.

More example for policy/risk/server bundles live in `docs/example-policies/`.

---

## Audit trail (SQLite)

* `requests`: intent ledger (server, tool, env, args hash)
* `decisions`: policy outcomes
* `events`: append-only timeline

Example:

```sql
select id, server, tool, status, risk_score
from requests
order by created_at desc
limit 10;
```

---

## Development

* Lint: `poetry run ruff check .`
* Tests: `poetry run pytest`
* DB migrations auto-apply via `ensure_db`

PRs and issues are welcome. Keep changes small and reliability-focused.
