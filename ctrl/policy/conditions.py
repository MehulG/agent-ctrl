from __future__ import annotations

from typing import Any, Dict
from ctrl.risk.expr import safe_eval

def requires_approval(expr: str | None, *, risk: Dict[str, Any]) -> bool:
    """
    Safe eval of approval condition.
    Available vars:
      risk.score, risk.mode  (exposed as risk_score, risk_mode + risk dict)
    """
    if not expr:
        return False

    # Provide both dot-less vars and dict
    ctx = {
        "risk": risk,
        "risk_score": risk.get("score", 0),
        "risk_mode": risk.get("mode", "safe"),
    }

    try:
        return bool(safe_eval(expr.replace("risk.score", "risk_score").replace("risk.mode", "risk_mode"), ctx))
    except Exception:
        # Fail-closed: require approval if expression is invalid
        return True
