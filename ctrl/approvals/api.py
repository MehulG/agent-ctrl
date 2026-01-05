from __future__ import annotations

import json
import logging
import uuid
from typing import Any, Dict, Optional
import os

import aiosqlite
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.tools import load_mcp_tools

from ctrl.config.loader import load_and_validate

# Quiet noisy session termination warnings when MCP servers return 404 on DELETE /mcp.
logging.getLogger("mcp.client.streamable_http").setLevel(logging.ERROR)

app = FastAPI(title="ctrl approvals")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_origin_regex=".*",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

DEFAULT_DB_PATH = os.environ.get("CTRL_DB_PATH", "ctrl.db")
DEFAULT_SERVERS_PATH = os.environ.get("CTRL_SERVERS_PATH", "configs/servers.yaml")
DEFAULT_POLICY_PATH = os.environ.get("CTRL_POLICY_PATH", "configs/policy.yaml")

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

def _connections_from_servers_yaml(servers_path: str | None = None) -> Dict[str, Dict[str, Any]]:
    servers_file = servers_path or DEFAULT_SERVERS_PATH
    servers_cfg, _ = load_and_validate(servers_path=servers_file, policy_path=DEFAULT_POLICY_PATH)
    conns: Dict[str, Dict[str, Any]] = {}
    for s in servers_cfg.servers:
        conn: Dict[str, Any] = {"transport": s.transport, "url": s.base_url}
        if s.transport == "http":
            conn["terminate_on_close"] = False
        conns[s.name] = conn
    return conns

async def _execute_tool(server: str, tool: str, args: Dict[str, Any], servers_path: str | None = None) -> Any:
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
async def pending(db_path: str = DEFAULT_DB_PATH):
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

@app.get("/requests")
async def requests(db_path: str = DEFAULT_DB_PATH, status: Optional[str] = None, limit: int = 200):
    status_filter = None if status is None else status.strip().lower()
    safe_limit = max(1, min(limit, 500))
    async with aiosqlite.connect(db_path) as db:
        if status_filter:
            rows = await _fetch_all(
                db,
                """
                SELECT id, created_at, server, tool, env, status, risk_score
                FROM requests
                WHERE status = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (status_filter, safe_limit),
            )
        else:
            rows = await _fetch_all(
                db,
                """
                SELECT id, created_at, server, tool, env, status, risk_score
                FROM requests
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (safe_limit,),
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
async def status(request_id: str, db_path: str = DEFAULT_DB_PATH):
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

        result_preview = None
        events = await _fetch_all(
            db,
            """
            SELECT data_json
            FROM events
            WHERE request_id = ?
            ORDER BY created_at DESC
            LIMIT 25
            """,
            (request_id,),
        )
        for row in events:
            if not row or not row[0]:
                continue
            try:
                payload = json.loads(row[0])
            except json.JSONDecodeError:
                continue
            if isinstance(payload, dict) and "result_preview" in payload:
                result_preview = payload.get("result_preview")
                break
        if result_preview is not None and not isinstance(result_preview, str):
            try:
                result_preview = json.dumps(result_preview, ensure_ascii=False)
            except TypeError:
                result_preview = str(result_preview)

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
                "result_preview": result_preview,
            },
            "decision": None if not d else {
                "decided_at": d[0],
                "decision": d[1],
                "policy_id": d[2],
                "reason": d[3],
            },
        }

@app.post("/deny/{request_id}")
async def deny(request_id: str, body: ApproveBody = ApproveBody(), db_path: str = DEFAULT_DB_PATH):
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
    db_path: str = DEFAULT_DB_PATH,
    servers_path: str = DEFAULT_SERVERS_PATH,
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
