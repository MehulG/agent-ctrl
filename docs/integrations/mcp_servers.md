# MCP servers

CtrlMCP reads a standard `servers.yaml` and builds connections for each MCP server.

## Server config shape
```yaml
servers:
  - name: coingecko
    transport: http            # http | ws (depends on the MCP server)
    base_url: https://mcp.api.coingecko.com/mcp

  - name: edgeone
    transport: http
    base_url: https://mcp-on-edge.edgeone.site/mcp-server
```

Guidelines:
- Use stable, lowercase names; they appear in policy matches and audit logs.
- Transport: ctrl currently supports `http` MCP servers only; keep `transport: http` in configs until other transports land.
- If two servers expose identical tool names, keep `tool_name_prefix=True` on CtrlMCP to avoid collisions; set to `False` to mirror MultiServer defaults.

## Validating connectivity
Run `ctrl validate-config --servers <path> --policy <path> --db ctrl.db` to ensure YAML shape is correct and the DB schema exists. The command does not reach out to servers; it validates structure only. Use the demo run or a simple agent call to confirm live connectivity to MCP endpoints.

## Per-environment overrides
- Pass `default_env` when constructing CtrlMCP to tag all calls (e.g., `dev`, `staging`, `prod`).
- Clients can override per request by setting the `x-ctrl-env` header in MCP calls; policies can match on this field.

## Adding new servers
1) Add an entry to `servers.yaml` with the name, transport, and URL/endpoint.
2) Add or update a policy to cover the new server.
3) Add risk rules if the server carries higher impact tools (e.g., deployers, data mutators).
4) Re-run `ctrl validate-config` and restart your agent.
