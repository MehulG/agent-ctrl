from __future__ import annotations

import ast
import math
from typing import Any, Dict


_ALLOWED_FUNCS = {
    "min": min,
    "max": max,
    "abs": abs,
    "round": round,
    "floor": math.floor,
    "ceil": math.ceil,
    "sqrt": math.sqrt,
    "log": math.log,
}

_ALLOWED_NODES = (
    ast.Expression,
    ast.BoolOp,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.Call,
    ast.Name,
    ast.Load,
    ast.Constant,
    ast.List,
    ast.Tuple,
    ast.cmpop,      # Eq, GtE, Lt, In, ...
    ast.boolop,     # And, Or
    ast.operator,   # Add, Sub, Mult, ...
    ast.unaryop,    # Not, USub, ...
)


_ALLOWED_BINOPS = (ast.Add, ast.Sub, ast.Mult, ast.Div, ast.Mod, ast.Pow)
_ALLOWED_UNARYOPS = (ast.UAdd, ast.USub, ast.Not)
_ALLOWED_BOOLOPS = (ast.And, ast.Or)
_ALLOWED_CMPOPS = (ast.Eq, ast.NotEq, ast.Gt, ast.GtE, ast.Lt, ast.LtE, ast.In, ast.NotIn)

def _deny(msg: str) -> None:
    raise ValueError(f"Unsafe expression: {msg}")

def _validate(node: ast.AST) -> None:
    for n in ast.walk(node):
        if not isinstance(n, _ALLOWED_NODES):
            _deny(f"disallowed node: {type(n).__name__}")

        # Block attribute access: foo.bar
        if isinstance(n, ast.Attribute):
            _deny("attribute access not allowed")

        # Block subscripting: a[0] (keeps it simple/safe)
        if isinstance(n, ast.Subscript):
            _deny("subscript not allowed")

        if isinstance(n, ast.Call):
            if not isinstance(n.func, ast.Name):
                _deny("only simple function calls allowed")
            if n.func.id not in _ALLOWED_FUNCS:
                _deny(f"function '{n.func.id}' not allowed")

        if isinstance(n, ast.BinOp) and not isinstance(n.op, _ALLOWED_BINOPS):
            _deny(f"binop '{type(n.op).__name__}' not allowed")

        if isinstance(n, ast.UnaryOp) and not isinstance(n.op, _ALLOWED_UNARYOPS):
            _deny(f"unaryop '{type(n.op).__name__}' not allowed")

        if isinstance(n, ast.BoolOp) and not isinstance(n.op, _ALLOWED_BOOLOPS):
            _deny(f"boolop '{type(n.op).__name__}' not allowed")

        if isinstance(n, ast.Compare):
            for op in n.ops:
                if not isinstance(op, _ALLOWED_CMPOPS):
                    _deny(f"compare op '{type(op).__name__}' not allowed")

        if isinstance(n, ast.Name):
            if n.id.startswith("__"):
                _deny("dunder names not allowed")

def safe_eval(expr: str, vars: Dict[str, Any]) -> Any:
    """
    Safely evaluate a restricted expression.
    Allowed: numbers, strings, booleans, comparisons, and/or/not,
    + - * / ** %, min/max/abs/round/floor/ceil/sqrt/log
    """
    node = ast.parse(expr, mode="eval")
    _validate(node)

    compiled = compile(node, "<risk-expr>", "eval")
    env = dict(_ALLOWED_FUNCS)
    env.update(vars)
    return eval(compiled, {"__builtins__": {}}, env)
