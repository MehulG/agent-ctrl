from __future__ import annotations

import hashlib
import json
import time
import uuid
from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Any, Awaitable, Callable, Optional

import aiosqlite
from langchain_mcp_adapters.client import MultiServerMCPClient
from langchain_mcp_adapters.interceptors import MCPToolCallRequest

from ctrl.config.loader import load_and_validate, load_risk_config
from ctrl.db.migrate import ensure_db
from ctrl.policy.conditions import requires_approval
from ctrl.risk.engine import RiskEngine


# ----------------------------
# Policy (v0): first match wins
# ----------------------------

@dataclass(frozen=True)
class Decision:
    decision: str  # "allow" | "deny" | "pending"
    policy_id: Optional[str]
    reason: str
    matched: str  # short string for debugging


def decide(policy_cfg, *, server: str, tool: str, env: str) -> Decision:
    for p in policy_cfg.policies:
        m = p.match
        if fnmatch(server, m.server) and fnmatch(tool, m.tool) and fnmatch(env, m.env):
            matched = f"server={m.server} tool={m.tool} env={m.env}"
            return Decision(decision=p.effect, policy_id=p.id, reason=p.reason, matched=matched)
    return Decision(decision="deny", policy_id=None, reason="No policy matched", matched="none")


def _get_policy_by_id(policy_cfg, policy_id: Optional[str]):
    if not policy_id:
        return None
    for p in policy_cfg.policies:
        if p.id == policy_id:
            return p
    return None


# ----------------------------
# DB helpers
# ----------------------------

def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _stable_json(obj: Any) -> str:
    return json.dumps(obj, separators=(",", ":"), sort_keys=True, ensure_ascii=False)


def _sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


async def db_insert_request(
    db_path: str,
    *,
    request_id: str,
    server: str,
    tool: str,
    arguments_json: str,
    arguments_hash: str,
    actor: Optional[str],
    env: str,
    status: str,
    risk_score: Optional[int] = None,
    risk_mode: Optional[str] = None,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO requests (
              id, created_at, server, tool, arguments_json, arguments_hash, actor, env, status, risk_score, risk_mode
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                request_id,
                _now_iso(),
                server,
                tool,
                arguments_json,
                arguments_hash,
                actor,
                env,
                status,
                risk_score,
                risk_mode,
            ),
        )
        await db.commit()


async def db_update_request_status(db_path: str, *, request_id: str, status: str) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute("UPDATE requests SET status = ? WHERE id = ?", (status, request_id))
        await db.commit()


async def db_update_request_risk(
    db_path: str,
    *,
    request_id: str,
    risk_score: Optional[int],
    risk_mode: Optional[str],
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            "UPDATE requests SET risk_score = ?, risk_mode = ? WHERE id = ?",
            (risk_score, risk_mode, request_id),
        )
        await db.commit()


async def db_insert_decision(
    db_path: str,
    *,
    decision_id: str,
    request_id: str,
    decision: str,
    matched_policy_id: Optional[str],
    matched_condition: str,
    reason: str,
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO decisions (
              id, request_id, decided_at, decision, matched_policy_id, matched_condition, reason
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (decision_id, request_id, _now_iso(), decision, matched_policy_id, matched_condition, reason),
        )
        await db.commit()


async def db_insert_event(
    db_path: str,
    *,
    event_id: str,
    request_id: Optional[str],
    type_: str,
    data: dict[str, Any],
) -> None:
    async with aiosqlite.connect(db_path) as db:
        await db.execute(
            """
            INSERT INTO events (
              id, created_at, request_id, type, data_json
            ) VALUES (?, ?, ?, ?, ?)
            """,
            (event_id, _now_iso(), request_id, type_, _stable_json(data)),
        )
        await db.commit()


# ----------------------------
# Interceptor: log → risk → decide → enforce → forward
# ----------------------------

class CtrlPolicyInterceptor:
    def __init__(self, *, db_path: str, policy_cfg, risk_engine: RiskEngine, default_env: str = "dev"):
        self.db_path = db_path
        self.policy_cfg = policy_cfg
        self.risk_engine = risk_engine
        self.default_env = default_env

    async def __call__(
        self,
        request: MCPToolCallRequest,
        handler: Callable[[MCPToolCallRequest], Awaitable[Any]],
    ) -> Any:
        server = getattr(request, "server_name", None) or "unknown"
        tool = getattr(request, "name", None) or "unknown"
        args = getattr(request, "args", None) or {}

        # env
        env = self.default_env
        headers = getattr(request, "headers", None) or {}
        if isinstance(headers, dict) and headers.get("x-ctrl-env"):
            env = str(headers["x-ctrl-env"])

        # actor (best-effort)
        actor = None
        runtime = getattr(request, "runtime", None)
        if runtime is not None:
            ctx = getattr(runtime, "context", None)
            if ctx is not None:
                actor = getattr(ctx, "user_id", None) or getattr(ctx, "actor", None)

        request_id = str(uuid.uuid4())
        args_json = _stable_json(args)
        args_hash = _sha256(args_json)

        # Risk first (so we can persist it on the request row)
        intent = {"server": server, "tool": tool, "env": env, "args": args, "actor": actor}
        risk_res = self.risk_engine.score(intent)
        risk = {
            "mode": risk_res.mode,
            "score": int(risk_res.score),
            "reasons": list(risk_res.reasons),
            "rules": list(risk_res.matched_rules),
        }

        # Persist intent with risk fields
        await db_insert_request(
            self.db_path,
            request_id=request_id,
            server=server,
            tool=tool,
            arguments_json=args_json,
            arguments_hash=args_hash,
            actor=actor,
            env=env,
            status="proposed",
            risk_score=risk["score"],
            risk_mode=risk["mode"],
        )

        await db_insert_event(
            self.db_path,
            event_id=str(uuid.uuid4()),
            request_id=request_id,
            type_="request.created",
            data={"server": server, "tool": tool, "env": env, "actor": actor},
        )

        await db_insert_event(
            self.db_path,
            event_id=str(uuid.uuid4()),
            request_id=request_id,
            type_="risk.scored",
            data=risk,
        )

        # Policy decide
        d = decide(self.policy_cfg, server=server, tool=tool, env=env)
        await db_insert_decision(
            self.db_path,
            decision_id=str(uuid.uuid4()),
            request_id=request_id,
            decision=d.decision,
            matched_policy_id=d.policy_id,
            matched_condition=d.matched,
            reason=d.reason,
        )
        await db_insert_event(
            self.db_path,
            event_id=str(uuid.uuid4()),
            request_id=request_id,
            type_="decision.made",
            data={"decision": d.decision, "policy_id": d.policy_id, "reason": d.reason, "matched": d.matched},
        )

        # Approval gating via require_approval_if (uses risk.score / risk.mode)
        matched_policy = _get_policy_by_id(self.policy_cfg, d.policy_id)
        if matched_policy and requires_approval(getattr(matched_policy, "require_approval_if", None), risk=risk):
            d = Decision(
                decision="pending",
                policy_id=d.policy_id,
                reason=f"Approval required ({getattr(matched_policy, 'require_approval_if', 'risk-gated')})",
                matched=d.matched,
            )
            await db_insert_event(
                self.db_path,
                event_id=str(uuid.uuid4()),
                request_id=request_id,
                type_="decision.overridden",
                data={"to": "pending", "because": "require_approval_if", "risk": risk},
            )

        # Enforce
        if d.decision == "deny":
            await db_update_request_status(self.db_path, request_id=request_id, status="denied")
            await db_insert_event(
                self.db_path,
                event_id=str(uuid.uuid4()),
                request_id=request_id,
                type_="request.denied",
                data={"reason": d.reason, "risk": risk},
            )
            raise PermissionError(f"ctrl denied tool call: {server}.{tool} — {d.reason}")

        if d.decision == "pending":
            await db_update_request_status(self.db_path, request_id=request_id, status="pending")
            await db_insert_event(
                self.db_path,
                event_id=str(uuid.uuid4()),
                request_id=request_id,
                type_="request.pending",
                data={"reason": d.reason, "risk": risk},
            )
            raise PermissionError(f"ctrl requires approval (pending): {server}.{tool} — {d.reason}")

        # allow → forward
        await db_update_request_status(self.db_path, request_id=request_id, status="allowed")
        await db_insert_event(
            self.db_path,
            event_id=str(uuid.uuid4()),
            request_id=request_id,
            type_="proxy.forwarding",
            data={"server": server, "tool": tool, "risk": risk},
        )

        try:
            result = await handler(request)
            await db_update_request_status(self.db_path, request_id=request_id, status="executed")
            await db_insert_event(
                self.db_path,
                event_id=str(uuid.uuid4()),
                request_id=request_id,
                type_="proxy.executed",
                data={"ok": True},
            )
            return result
        except Exception as e:
            await db_update_request_status(self.db_path, request_id=request_id, status="failed")
            await db_insert_event(
                self.db_path,
                event_id=str(uuid.uuid4()),
                request_id=request_id,
                type_="proxy.failed",
                data={"error": repr(e)},
            )
            raise


# ----------------------------
# Public wrapper: CtrlMCP
# ----------------------------

class CtrlMCP:
    """
    LangChain-first entry point.

    - Loads servers.yaml + policy.yaml (+ risk.yaml)
    - Ensures DB is initialized (tables + columns)
    - Builds MultiServerMCPClient(connections, tool_interceptors=[...])
    - Exposes get_tools() returning normal LangChain tools
    """

    def __init__(
        self,
        *,
        servers: str = "configs/servers.yaml",
        policy: str = "configs/policy.yaml",
        risk: str = "configs/risk.yaml",
        db_path: str = "ctrl.db",
        default_env: str = "dev",
        tool_name_prefix: bool = False,
    ):
        self._servers_path = servers
        self._policy_path = policy
        self._risk_path = risk
        self._db_path = db_path
        self._default_env = default_env
        self._tool_name_prefix = tool_name_prefix

        ensure_db(db_path=self._db_path)

        self._servers_cfg, self._policy_cfg = load_and_validate(
            servers_path=self._servers_path,
            policy_path=self._policy_path,
        )

        self._risk_cfg = load_risk_config(risk_path=self._risk_path)
        self._risk_engine = RiskEngine(self._risk_cfg)

        connections: dict[str, dict[str, Any]] = {}
        for s in self._servers_cfg.servers:
            connections[s.name] = {"transport": s.transport, "url": s.base_url}

        interceptor = CtrlPolicyInterceptor(
            db_path=self._db_path,
            policy_cfg=self._policy_cfg,
            risk_engine=self._risk_engine,
            default_env=self._default_env,
        )

        self._client = MultiServerMCPClient(
            connections,
            tool_interceptors=[interceptor],
            tool_name_prefix=self._tool_name_prefix,
        )

    async def get_tools(self):
        return await self._client.get_tools()

    async def aclose(self):
        return None

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False
