from typing import List, Literal, Optional, Dict
from pydantic import BaseModel, Field, field_validator

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

class PolicyConfig(BaseModel):
    policies: List[Policy]

    @field_validator("policies")
    @classmethod
    def unique_policy_ids(cls, v):
        ids = [p.id for p in v]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate policy.id found")
        return v
