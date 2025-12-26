from __future__ import annotations

import json
import uuid
from typing import Any, Dict, Optional

import aiosqlite
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from ctrl.config.loader import load_and_validate

app = FastAPI(title="ctrl approvals")

class ApproveBody(BaseModel):
    approved_by: Optional[str] = "human"

def _now_iso():
    import time
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())

async def _fetch_one(db, q: str, params=()):
    cur = await db.execute(q, params)
    row = await cur.fetchone()
    await cur.close()
    return row

async def _fetch_all(db, q: str, params=()):
    cur = await db.execute(q, params)
    rows = await cur.fetchall()
    await cur.close()
    return rows

async def _event(db, request_id: str | None, type_: str, data: Dict[str, Any]):
    await db.execute(
        "INSERT INTO events (id, created_at, request_id, type, data_json) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), _now_iso(), request_id, type_, json.dumps(data, separators=(",", ":"), sort_keys=True)),
    )

def _connections_from_servers_yaml(servers_path: str) -> Dict[str, Dict[str, Any]]:
    servers_cfg, _ = load_and_validate(servers_path=servers_path, policy_path="configs/policy.yaml")
    conns: Dict[str, Dict[str, Any]] = {}
    for s in servers_cfg.servers:
        conns[s.name] = {"transport": s.transport, "url": s.base_url}
    return conns

async def _execute_tool(server: str, tool: str, args: Dict[str, Any], servers_path: str) -> Any:
    conns = _connections_from_servers_yaml(servers_path)
    client = MultiServerMCPClient(conns, tool_interceptors=[], tool_name_prefix=False)

    async with client.session(server) as session:
        tools = await load_mcp_tools(session)

        chosen = next((t for t in tools if t.name == tool), None)
        if not chosen:
            available = [t.name for t in tools]
            raise RuntimeError(f"Tool not found: {tool}. Available: {available}")

        return await chosen.ainvoke(args)


@app.get("/pending")
async def pending(db_path: str = "ctrl.db"):
    async with aiosqlite.connect(db_path) as db:
        rows = await _fetch_all(
            db,
            """
            SELECT id, created_at, server, tool, env, status, risk_score
            FROM requests
            WHERE status = 'pending'
            ORDER BY created_at DESC
            LIMIT 200
            """,
        )
        return [
            {
                "id": r[0],
                "created_at": r[1],
                "server": r[2],
                "tool": r[3],
                "env": r[4],
                "status": r[5],
                "risk_score": r[6],
            }
            for r in rows
        ]

@app.get("/status/{request_id}")
async def status(request_id: str, db_path: str = "ctrl.db"):
    async with aiosqlite.connect(db_path) as db:
        r = await _fetch_one(
            db,
            "SELECT id, created_at, server, tool, env, status, risk_score, arguments_json FROM requests WHERE id = ?",
            (request_id,),
        )
        if not r:
            raise HTTPException(404, "request not found")

        d = await _fetch_one(
            db,
            """
            SELECT decided_at, decision, matched_policy_id, reason
            FROM decisions
            WHERE request_id = ?
            ORDER BY decided_at DESC
            LIMIT 1
            """,
            (request_id,),
        )

        return {
            "request": {
                "id": r[0],
                "created_at": r[1],
                "server": r[2],
                "tool": r[3],
                "env": r[4],
                "status": r[5],
                "risk_score": r[6],
                "arguments": json.loads(r[7]) if r[7] else {},
            },
            "decision": None if not d else {
                "decided_at": d[0],
                "decision": d[1],
                "policy_id": d[2],
                "reason": d[3],
            },
        }

@app.post("/deny/{request_id}")
async def deny(request_id: str, body: ApproveBody = ApproveBody(), db_path: str = "ctrl.db"):
    async with aiosqlite.connect(db_path) as db:
        r = await _fetch_one(db, "SELECT status FROM requests WHERE id = ?", (request_id,))
        if not r:
            raise HTTPException(404, "request not found")
        if r[0] != "pending":
            raise HTTPException(400, f"request not pending (status={r[0]})")

        await db.execute("UPDATE requests SET status = ? WHERE id = ?", ("denied", request_id))
        await _event(db, request_id, "approval.denied", {"by": body.approved_by})
        await db.commit()
        return {"ok": True, "status": "denied"}

@app.post("/approve/{request_id}")
async def approve(
    request_id: str,
    body: ApproveBody = ApproveBody(),
    db_path: str = "ctrl.db",
    servers_path: str = "configs/servers.yaml",
):
    async with aiosqlite.connect(db_path) as db:
        r = await _fetch_one(
            db,
            "SELECT server, tool, arguments_json, status FROM requests WHERE id = ?",
            (request_id,),
        )
        if not r:
            raise HTTPException(404, "request not found")
        if r[3] != "pending":
            raise HTTPException(400, f"request not pending (status={r[3]})")

        server, tool, args_json = r[0], r[1], r[2]
        args = json.loads(args_json) if args_json else {}

        # mark approved
        await db.execute(
            "UPDATE requests SET status = ?, approved_at = ?, approved_by = ? WHERE id = ?",
            ("approved", _now_iso(), body.approved_by, request_id),
        )
        await _event(db, request_id, "approval.granted", {"by": body.approved_by})
        await db.commit()

    # execute outside DB transaction
    try:
        result = await _execute_tool(server=server, tool=tool, args=args, servers_path=servers_path)
    except Exception as e:
        async with aiosqlite.connect(db_path) as db:
            await db.execute("UPDATE requests SET status = ? WHERE id = ?", ("failed", request_id))
            await _event(db, request_id, "proxy.failed", {"error": repr(e)})
            await db.commit()
        raise HTTPException(500, f"execution failed: {e!r}")

    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE requests SET status = ? WHERE id = ?", ("executed", request_id))
        await _event(db, request_id, "proxy.executed", {"ok": True})
        await _event(db, request_id, "tool.result", {"result_preview": str(result)[:500]})
        await db.commit()

    return {"ok": True, "status": "executed"}
