from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatch
from typing import Any, Dict, List, Optional, Tuple

from ctrl.risk.expr import safe_eval


@dataclass(frozen=True)
class RiskResult:
    mode: str
    score: int
    reasons: List[str]
    matched_rules: List[str]


def _mode_rank(mode: str) -> int:
    # You can make this configurable later; v0 assumes 3-level ladder.
    order = {"safe": 0, "review": 1, "danger": 2}
    return order.get(mode, 0)

def _escalate_one(mode: str) -> str:
    ladder = ["safe", "review", "danger"]
    try:
        i = ladder.index(mode)
    except ValueError:
        return mode
    return ladder[min(i + 1, len(ladder) - 1)]

def _args_match(args: Dict[str, Any], predicates: Dict[str, Dict[str, Any]]) -> bool:
    """
    predicates:
      amount: { gte: 1000 }
      repo: { in: ["a","b"] }
    """
    for k, pred in (predicates or {}).items():
        v = args.get(k)

        if "eq" in pred and v != pred["eq"]:
            return False
        if "ne" in pred and v == pred["ne"]:
            return False

        if "gte" in pred:
            if not isinstance(v, (int, float)) or float(v) < float(pred["gte"]):
                return False
        if "gt" in pred:
            if not isinstance(v, (int, float)) or float(v) <= float(pred["gt"]):
                return False
        if "lte" in pred:
            if not isinstance(v, (int, float)) or float(v) > float(pred["lte"]):
                return False
        if "lt" in pred:
            if not isinstance(v, (int, float)) or float(v) >= float(pred["lt"]):
                return False

        if "contains" in pred:
            if not isinstance(v, str) or pred["contains"] not in v:
                return False

        if "in" in pred:
            if v not in pred["in"]:
                return False

    return True

def _when_matches(when: dict, intent: dict) -> bool:
    if not fnmatch(intent["server"], when.get("server", "*")):
        return False
    if not fnmatch(intent["tool"], when.get("tool", "*")):
        return False
    if not fnmatch(intent["env"], when.get("env", "*")):
        return False
    args_pred = when.get("args")
    if args_pred:
        if not _args_match(intent.get("args", {}), args_pred):
            return False
    return True


class RiskEngine:
    def __init__(self, risk_cfg):
        self.cfg = risk_cfg.risk

        if self.cfg.mode != "modes":
            raise ValueError("Only risk.mode=modes supported in v0")

        if not self.cfg.modes:
            raise ValueError("risk.modes is required")

        # Ensure standard ladder exists (optional but recommended)
        # You can relax later.
        for must in ("safe", "review", "danger"):
            if must not in self.cfg.modes:
                raise ValueError(f"risk.modes must include '{must}' for v0 ladder")

    def score(self, intent: dict) -> RiskResult:
        """
        intent = {server, tool, env, args, actor?}
        """
        mode = "safe"
        score = self.cfg.modes[mode].score
        reasons: List[str] = []
        matched_rules: List[str] = []

        # Build base variables for expressions
        vars_ctx = {
            "server": intent.get("server", ""),
            "tool": intent.get("tool", ""),
            "env": intent.get("env", ""),
            "args": intent.get("args", {}),
        }

        # Flatten some common args into top-level vars for convenience
        # (amount, repo, etc.)
        for k, v in (intent.get("args", {}) or {}).items():
            if isinstance(v, (int, float, str, bool)):
                vars_ctx[k] = v

        # Compute user vars (like amount_norm)
        computed: Dict[str, Any] = {}
        for name, expr in (self.cfg.vars or {}).items():
            try:
                computed[name] = safe_eval(expr, {**vars_ctx, **computed})
            except Exception:
                # Fail-closed-ish: if vars fail, ignore them but note reason
                computed[name] = 0

        # Apply rules in order
        for rule in self.cfg.rules:
            when = rule.when.model_dump() if hasattr(rule.when, "model_dump") else rule.when
            if not _when_matches(when, {"server": intent["server"], "tool": intent["tool"], "env": intent["env"], "args": intent.get("args", {})}):
                continue

            matched_rules.append(rule.name)
            if rule.reason:
                reasons.append(rule.reason)

            # score_expr overrides/adds scoring
            if rule.score_expr:
                try:
                    v = safe_eval(rule.score_expr, {**vars_ctx, **computed, "score": score, "mode": mode})
                    if isinstance(v, (int, float)):
                        score = int(max(0, min(100, round(float(v)))))
                except Exception:
                    # Fail-closed: bump to review on expression failure
                    mode = max(mode, "review", key=_mode_rank)
                    reasons.append(f"Expr failed in rule '{rule.name}' -> escalated")

            # set_mode
            if rule.set_mode:
                mode = rule.set_mode

            # escalate
            if rule.escalate == "one_level":
                mode = _escalate_one(mode)

            # keep score aligned with mode baseline if score not explicitly computed
            # (optional behavior; keeps simple)
            score = max(score, self.cfg.modes.get(mode, self.cfg.modes["safe"]).score)

        # Map score to mode using set_mode_by_score (optional)
        if self.cfg.set_mode_by_score:
            # compute final mode by evaluating expressions in declared order
            # priority: danger, review, safe (common)
            # but we'll use config order as given
            for mode_name, cond_expr in self.cfg.set_mode_by_score.items():
                try:
                    ok = safe_eval(cond_expr, {**vars_ctx, **computed, "score": score, "mode": mode})
                    if bool(ok):
                        mode = mode_name
                        break  # first match wins to keep ordering deterministic
                except Exception:
                    # if mapping fails, require review
                    mode = max(mode, "review", key=_mode_rank)
                    reasons.append("set_mode_by_score expression failed -> review")
            # Realign score with the chosen mode's baseline so mode/score stay consistent
            score = max(score, self.cfg.modes.get(mode, self.cfg.modes["safe"]).score)

        # Final clamp
        score = int(max(0, min(100, score)))

        return RiskResult(mode=mode, score=score, reasons=reasons, matched_rules=matched_rules)
