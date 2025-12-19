from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Any, Optional


@dataclass(frozen=True)
class PolicyMatchResult:
    decision: str  # allow|deny|pending
    policy_id: Optional[str]
    reason: str
    matched: str  # "server=... tool=... env=..."
    index: int  # policy order


def decide_explain(policy_cfg, *, server: str, tool: str, env: str) -> PolicyMatchResult:
    """
    First-match-wins wildcard matching using fnmatch (* patterns).
    policy_cfg is ctrl.config.schema.PolicyConfig (pydantic).
    """
    for i, p in enumerate(policy_cfg.policies):
        m = p.match
        if fnmatch(server, m.server) and fnmatch(tool, m.tool) and fnmatch(env, m.env):
            matched = f"server={m.server} tool={m.tool} env={m.env}"
            return PolicyMatchResult(
                decision=p.effect,
                policy_id=p.id,
                reason=p.reason or "",
                matched=matched,
                index=i,
            )
    return PolicyMatchResult(
        decision="deny",
        policy_id=None,
        reason="No policy matched",
        matched="none",
        index=-1,
    )


def _subsumes(a: str, b: str) -> bool:
    """
    Heuristic: does pattern 'a' match everything that pattern 'b' would match?
    Strong check is hard; for v0 we treat '*' as universal, otherwise assume not.
    """
    return a == "*" or a == b


def lint_policy(policy_cfg) -> dict[str, list[str]]:
    """
    Returns {"errors": [...], "warnings": [...]}.
    v0 rules:
    - warn if no catch-all default policy exists
    - warn about obvious shadowing: earlier rule with server/tool/env == '*' shadows later rules
      (or exact-equal subsumption).
    """
    errors: list[str] = []
    warnings: list[str] = []

    policies = policy_cfg.policies

    # Catch-all check
    has_catch_all = False
    for p in policies:
        m = p.match
        if m.server == "*" and m.tool == "*" and m.env == "*":
            has_catch_all = True
            break
    if not has_catch_all:
        warnings.append("No catch-all policy found (match: server='*', tool='*', env='*').")

    # Shadowing check (simple + useful)
    for i, p_i in enumerate(policies):
        m_i = p_i.match
        for j in range(i + 1, len(policies)):
            p_j = policies[j]
            m_j = p_j.match

            if _subsumes(m_i.server, m_j.server) and _subsumes(m_i.tool, m_j.tool) and _subsumes(m_i.env, m_j.env):
                warnings.append(
                    f"Policy '{p_i.id}' (index {i}) likely shadows '{p_j.id}' (index {j}). "
                    f"Earlier: server={m_i.server}, tool={m_i.tool}, env={m_i.env} "
                    f"Later: server={m_j.server}, tool={m_j.tool}, env={m_j.env}"
                )

    # Pending check (since approvals aren't built yet)
    for p in policies:
        if p.effect == "pending":
            warnings.append(f"Policy '{p.id}' uses effect=pending but approvals aren't implemented yet (Day 4).")

    return {"errors": errors, "warnings": warnings}


def run_policy_tests(policy_cfg, tests_cfg: dict[str, Any]) -> tuple[int, list[str]]:
    """
    tests_cfg example:
      {"tests":[{"name":"...", "input":{"server":"x","tool":"y","env":"dev"}, "expect":"deny"}]}
    Returns (fail_count, lines).
    """
    tests = tests_cfg.get("tests", [])
    lines: list[str] = []
    fails = 0

    if not isinstance(tests, list):
        return 1, ["tests must be a list"]

    for t in tests:
        name = t.get("name", "<unnamed>")
        inp = t.get("input", {}) or {}
        exp = t.get("expect")

        server = inp.get("server", "")
        tool = inp.get("tool", "")
        env = inp.get("env", "")

        got = decide_explain(policy_cfg, server=server, tool=tool, env=env).decision
        ok = (got == exp)

        if ok:
            lines.append(f"✓ {name}  ({server}.{tool} env={env}) => {got}")
        else:
            fails += 1
            lines.append(f"✗ {name}  ({server}.{tool} env={env}) => got {got}, expected {exp}")

    return fails, lines
