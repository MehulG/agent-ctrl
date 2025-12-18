import yaml
from ctrl.config.schema import ServersConfig, PolicyConfig

def _read_yaml(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path} must be a YAML mapping/object at top level")
    return data

def load_and_validate(servers_path: str, policy_path: str) -> tuple[ServersConfig, PolicyConfig]:
    servers_raw = _read_yaml(servers_path)
    policy_raw = _read_yaml(policy_path)

    servers_cfg = ServersConfig.model_validate(servers_raw)
    policy_cfg = PolicyConfig.model_validate(policy_raw)

    return servers_cfg, policy_cfg
