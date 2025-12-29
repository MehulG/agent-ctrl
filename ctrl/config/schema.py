from __future__ import annotations
from pydantic import BaseModel, Field, field_validator
from typing import Any, Dict, List, Literal, Optional


class Server(BaseModel):
    name: str
    transport: Literal["http"]
    base_url: str

class ServersConfig(BaseModel):
    servers: List[Server]
    defaults: Optional[Dict[str, str]] = None

    @field_validator("servers")
    @classmethod
    def unique_server_names(cls, v):
        names = [s.name for s in v]
        if len(names) != len(set(names)):
            raise ValueError("duplicate server.name found")
        return v

class PolicyMatch(BaseModel):
    server: str = "*"
    tool: str = "*"
    env: str = "*"

class Policy(BaseModel):
    id: str
    match: PolicyMatch
    effect: Literal["allow", "deny", "pending"]
    reason: str = ""
    deny: Optional[str] = None
    require_approval_if: Optional[str] = None

class PolicyConfig(BaseModel):
    policies: List[Policy]

    @field_validator("policies")
    @classmethod
    def unique_policy_ids(cls, v):
        ids = [p.id for p in v]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate policy.id found")
        return v




class RiskMode(BaseModel):
    score: int


class RiskRuleWhenArgPredicate(BaseModel):
    # Only one of these should be present
    eq: Optional[Any] = None
    ne: Optional[Any] = None
    gte: Optional[float] = None
    gt: Optional[float] = None
    lte: Optional[float] = None
    lt: Optional[float] = None
    contains: Optional[str] = None
    in_: Optional[List[Any]] = Field(default=None, alias="in")


class RiskRuleWhen(BaseModel):
    server: str = "*"
    tool: str = "*"
    env: str = "*"
    # args is a map: arg_name -> predicate dict
    args: Optional[Dict[str, Dict[str, Any]]] = None


class RiskRule(BaseModel):
    name: str = "rule"
    when: RiskRuleWhen
    reason: str = ""

    # Actions (only one typically used)
    set_mode: Optional[str] = None
    escalate: Optional[Literal["one_level"]] = None

    # Optional scoring
    score_expr: Optional[str] = None


class RiskConfig(BaseModel):
    mode: Literal["modes"] = "modes"
    modes: Dict[str, RiskMode]  # safe/review/danger -> score mapping
    vars: Dict[str, str] = Field(default_factory=dict)  # name -> expr
    rules: List[RiskRule] = Field(default_factory=list)
    set_mode_by_score: Dict[str, str] = Field(default_factory=dict)  # mode -> expr


class RootRiskConfig(BaseModel):
    risk: RiskConfig
