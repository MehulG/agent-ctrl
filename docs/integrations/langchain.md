# LangChain integration

CtrlMCP is a drop-in replacement for `MultiServerMCPClient`. It loads your server, policy, and risk configs, attaches an interceptor, and returns normal LangChain tools.

## Minimal wiring
```python
from ctrl.langchain.client import CtrlMCP

mcp = CtrlMCP(
    servers="configs/servers.yaml",
    policy="configs/policy.yaml",
    risk="configs/risk.yaml",
    db_path="ctrl.db",
    default_env="dev",           # overridable with x-ctrl-env header
    tool_name_prefix=False,      # mirrors MultiServerMCPClient behavior
    return_on_pending=False,     # raise on pending by default; change to True if want to exit gracefully
)

tools = await mcp.get_tools()
agent = create_agent(ChatOpenAI(model="gpt-4o-mini"), tools)
response = await agent.ainvoke({"messages": [("user", "run a safe tool")]})
```

## Pending behavior
- Default: a `pending` decision raises `PermissionError` with the request ID (expected control-plane outcome; no tool is executed).
- Demo behavior: set `return_on_pending=True` to surface the pending payload in the agent response (used in `demos/e2e_publish_market_report/agent.py`). This lets the agent print `Waiting for approval: <id>` and exit 0.
- Approve via the API (`ctrl approvals-serve`) and the tool call is replayed with the original arguments.

## Environment and actor hints
- `default_env` sets the environment attached to each request. Agents can override per call via the `x-ctrl-env` header in MCP requests.
- If the runtime context contains `actor` (e.g., user ID or workspace), it is captured on the request record for auditing.

## Development tips
- Keep policies permissive while developing (`effect: allow` with `require_approval_if`) to avoid blocking iteration.
- Use `ctrl policy explain --server <name> --tool <name>` when a tool is unexpectedly denied.
- Pair with the dashboard (`dashboard/`) to review arguments, decisions, and approval status in real time.
