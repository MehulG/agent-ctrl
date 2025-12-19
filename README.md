# ctrl

**ctrl** is an execution control plane for AI agents.

It sits between an agent and its tools (MCP servers), and enforces **policies** before actions execute — while creating a durable **audit trail** of every tool call.

Today, ctrl ships a **LangChain-first integration**:
- Drop-in replacement for `MultiServerMCPClient`
- Policy enforcement on every MCP tool call
- SQLite-backed logs (`requests`, `decisions`, `events`)
- Policy UX: `lint`, `explain`, and `test`

> Status: early v0. Expect breaking changes as we iterate.

---

## Why ctrl exists

Traditional authorization (RBAC/ABAC) answers:
> “Is user X allowed to do Y?”

Agents need an execution firewall that answers:
> “Should this *specific agent intent* execute *right now*, in *this context*?”

Agents are non-deterministic. ctrl assumes actions must be:
- **inspectable**
- **explainable**
- **interruptible (soon)**
- **auditable**

---

## What’s included (current)

### ✅ Day 1
- `ctrl` CLI
- YAML config validation
- SQLite database + migrations:
  - `requests` — intent ledger
  - `decisions` — policy outcomes
  - `events` — timeline/audit

### ✅ Day 2
- LangChain MCP interception via `CtrlMCP`
- Policy enforcement (allow/deny/pending)
- Durable logging into SQLite
- Works with real MCP servers (e.g., Context7)

### ✅ Day 3
- Policy UX commands:
  - `ctrl policy lint`
  - `ctrl policy explain`
  - `ctrl policy test`

---

## Install

### Requirements
- Python 3.11+ (3.12 is fine)
- Poetry

### Setup
```bash
git clone <your-repo-url>
cd ctrl
poetry install
````

Run:

```bash
poetry run ctrl version
```

---

## Quickstart (LangChain + MCP)

### 1) Create configs

`configs/servers.yaml`

```yaml
servers:
  - name: context7
    transport: http
    base_url: "https://mcp.context7.com/mcp"

defaults:
  env: dev
```

`configs/policy.yaml`

```yaml
policies:
  - id: deny-prod-delete
    match:
      server: "*"
      tool: "*delete*"
      env: "prod"
    effect: deny
    reason: "Deletes in prod blocked (v0)"

  - id: allow-default
    match:
      server: "*"
      tool: "*"
      env: "*"
    effect: allow
    reason: "Default allow"
```

### 2) Validate config + init DB

```bash
poetry run ctrl validate-config --servers configs/servers.yaml --policy configs/policy.yaml --db ctrl.db
```

### 3) Use ctrl in your LangChain script

Replace this:

```py
from langchain_mcp_adapters.client import MultiServerMCPClient
mcp = MultiServerMCPClient({...})
```

With this:

```py
from ctrl.langchain.client import CtrlMCP

mcp = CtrlMCP(
    servers="configs/servers.yaml",
    policy="configs/policy.yaml",
    db_path="ctrl.db",
    default_env="dev",
)

tools = await mcp.get_tools()
```

Everything downstream stays the same: `create_agent(...)`, `agent.ainvoke(...)`, etc.

---

## How policy works (v0)

Policies are evaluated **in order** (first match wins).

Match fields support wildcards (`*`) via shell-style matching:

* `server`
* `tool`
* `env`

Effects:

* `allow` → forward tool call to MCP server
* `deny` → block tool call (raises `PermissionError`)
* `pending` → currently blocks (Day 4 turns this into approvals)

Example rule:

```yaml
- id: deny-prod-delete
  match: { server: "*", tool: "*delete*", env: "prod" }
  effect: deny
  reason: "Deletes in prod blocked (v0)"
```

---

## Inspect interceptions (logs)

All tool calls are written to SQLite.

Tables:

* `requests`: what the agent tried
* `decisions`: which policy matched + why
* `events`: append-only timeline

### CLI / SQL

```bash
sqlite3 ctrl.db
```

```sql
.headers on
.mode column

select id, created_at, server, tool, status
from requests
order by created_at desc
limit 20;

select d.decided_at, r.server, r.tool, d.decision, d.matched_policy_id, d.reason
from decisions d
join requests r on r.id = d.request_id
order by d.decided_at desc
limit 20;
```

### Quick GUI options

* **DB Browser for SQLite** (open `ctrl.db`)
* `sqlite-web`:

  ```bash
  poetry add sqlite-web
  poetry run sqlite_web ctrl.db
  ```

  Then open `http://localhost:8080`.

---

## Policy UX (Day 3)

### `lint`

Catches common mistakes (shadowing, missing catch-all, pending without approvals, etc.)

```bash
poetry run ctrl policy lint --policy configs/policy.yaml
```

### `explain`

Predicts what will happen for a hypothetical call:

```bash
poetry run ctrl policy explain --server context7 --tool "search_docs" --env dev
```

### `test`

Run a small suite of expected outcomes:

`configs/policy_tests.yaml`

```yaml
tests:
  - name: prod delete denied
    input: { server: github, tool: delete_repo, env: prod }
    expect: deny

  - name: context7 allowed
    input: { server: context7, tool: anything, env: dev }
    expect: allow
```

Run:

```bash
poetry run ctrl policy test configs/policy_tests.yaml --policy configs/policy.yaml
```

---

## Project layout

```
ctrl/
  cli/
    main.py            # ctrl CLI
    policy.py          # ctrl policy lint/explain/test
  config/
    loader.py          # YAML load + validate
    schema.py          # pydantic schemas
  db/
    migrate.py         # sqlite migrations
  langchain/
    client.py          # CtrlMCP wrapper + interceptor
  policy/
    core.py            # policy engine + lint/test helpers

configs/
  servers.yaml
  policy.yaml
  policy_tests.yaml

migrations/
  001_init.sql
```

---

## Roadmap (next)

* Day 4: approvals (turn `pending` into human-in-the-loop)
* Day 5: “killer demo” + templates + `ctrl demo up`
* Better actor identity + env propagation
* More expressive conditions (args-based rules)
* Risk scoring (heuristics)

---

## Contributing

Issues + PRs welcome.

* Keep changes small and testable
* Prefer additive changes (we’re iterating fast)

Suggested dev tools:

```bash
poetry run ruff check .
poetry run pytest
```

---

## License

TBD (MIT/Apache-2.0 are typical for OSS — pick one before wider distribution).
