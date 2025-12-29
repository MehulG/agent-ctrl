from __future__ import annotations

from typing import Any, Dict
from ctrl.risk.expr import safe_eval

def _eval_condition(expr: str | None, *, risk: Dict[str, Any], default_on_error: bool) -> bool:
    if not expr:
        return False

    ctx = {
        "risk": risk,
        "risk_score": risk.get("score", 0),
        "risk_mode": risk.get("mode", "safe"),
    }

    try:
        return bool(safe_eval(expr.replace("risk.score", "risk_score").replace("risk.mode", "risk_mode"), ctx))
    except Exception:
        return default_on_error

def requires_approval(expr: str | None, *, risk: Dict[str, Any]) -> bool:
    """
    Safe eval of approval condition.
    Available vars:
      risk.score, risk.mode  (exposed as risk_score, risk_mode + risk dict)
    """
    # Fail-closed: require approval if expression is invalid
    return _eval_condition(expr, risk=risk, default_on_error=True)

def denies_action(expr: str | None, *, risk: Dict[str, Any]) -> bool:
    """
    Safe eval of deny condition.
    Available vars:
      risk.score, risk.mode  (exposed as risk_score, risk_mode + risk dict)
    """
    # Fail-closed: deny if expression is invalid
    return _eval_condition(expr, risk=risk, default_on_error=True)
