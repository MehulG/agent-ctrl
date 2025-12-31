# Concepts

ctrl is an execution control plane for MCP tools. Every tool call is captured, risk-scored, evaluated against policy, and recorded in an auditable ledger.

## Control-plane flow
1) **Intent capture** — incoming server/tool/env/arguments are hashed and stored as a `requests` row (`status=proposed`).
2) **Risk scoring** — YAML-driven rules assign a numeric score and mode (`safe`, `review`, `danger`) based on server/tool/env/args. Results are persisted on the request and emitted as events.
3) **Policy evaluation** — ordered policies match on server/tool/env and optionally on risk context. Effects: `allow`, `deny`, `pending`. `require_approval_if` can override `allow` to `pending`.
4) **Enforcement** — `deny` halts immediately; `allow` forwards to the MCP server; `pending` records the request and waits for human approval.
5) **Approval + replay** — the approvals API updates the request to `approved`/`denied`, replays the tool call when approved, and appends new events.

## Policy model
- **First match wins:** policies are evaluated top-to-bottom.
- **Match fields:** `server`, `tool`, `env` support shell-style wildcards (`*`, `?`).
- **Effects:** `allow`, `deny`, `pending`. Use `require_approval_if` to gate allows based on expressions such as `risk.mode in ['review']`.
- **Conditional deny:** when using the `effect: allow` pattern, you can add `deny: "<expression>"` to block specific high-risk cases.
- **Explain/test:** `ctrl policy explain` shows which policy would fire; `ctrl policy test` runs fixtures through the engine.

## Risk model
- **Modes and baselines:** each mode has a baseline score; rules can set a mode, escalate a mode, or compute scores via expressions.
- **Rule triggers:** match on `server`, `tool`, `env`, and nested argument patterns (e.g., checking for `<script` inside HTML).
- **Mode mapping:** `set_mode_by_score` keeps numeric scores and named modes aligned.
- **Expressions:** evaluated via a sandbox (`ctrl/risk/expr.py`) with access to request context and rule matches.

## Pending + approvals
- When policy returns `pending`, ctrl stops before execution and records the request; the originating agent does not resume automatically.
- LangChain clients can either raise `PermissionError` (default) or return the pending payload by setting `return_on_pending=True` (used in the demo).
- The approvals API (`ctrl approvals-serve`) exposes `GET /pending`, `GET /status/{id}`, and `POST /approve|/deny/{id}` to resolve items. Approved requests are executed later via the approvals service against the original MCP server; fetch results from the dashboard or `GET /status/{id}`.

## Ledger (SQLite)
- **requests:** intent ledger with hashes of arguments, actor, env, risk mode/score, and status (`proposed`, `pending`, `allowed`, `denied`, `executed`, `failed`).
- **decisions:** policy outcome, matched policy ID, and the condition that triggered it.
- **events:** append-only trail of lifecycle steps (`request.created`, `risk.scored`, `decision.made`, `proxy.sent`, `approval.approved`, etc.).

Use `sqlite3 ctrl.db` or the dashboard to review what the agent attempted and how ctrl responded.
