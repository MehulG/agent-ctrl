from __future__ import annotations

import json
from pathlib import Path

import typer
import yaml
from rich import print

from ctrl.config.loader import load_and_validate
from ctrl.policy.core import decide_explain, lint_policy, run_policy_tests

app = typer.Typer(help="Policy tools: lint, explain, test")


@app.command("lint")
def lint(
    policy: str = typer.Option("configs/policy.yaml", "--policy"),
):
    _, policy_cfg = load_and_validate(servers_path="configs/servers.yaml", policy_path=policy)
    out = lint_policy(policy_cfg)

    for w in out["warnings"]:
        print(f"[yellow]WARN[/yellow] {w}")
    for e in out["errors"]:
        print(f"[red]ERR[/red]  {e}")

    if out["errors"]:
        raise typer.Exit(code=1)
    print("[green]OK[/green]")


@app.command("explain")
def explain(
    server: str = typer.Option(..., "--server"),
    tool: str = typer.Option(..., "--tool"),
    env: str = typer.Option("dev", "--env"),
    policy: str = typer.Option("configs/policy.yaml", "--policy"),
    args: str = typer.Option("", "--args", help="Optional JSON args (stored/display only)"),
):
    # args are optional today; kept for future explainability/risk scoring.
    parsed_args = None
    if args:
        try:
            parsed_args = json.loads(args)
        except Exception:
            raise typer.BadParameter("--args must be valid JSON")

    _, policy_cfg = load_and_validate(servers_path="configs/servers.yaml", policy_path=policy)
    res = decide_explain(policy_cfg, server=server, tool=tool, env=env)

    print("[bold]Decision[/bold]:", res.decision)
    print("[bold]Matched policy[/bold]:", res.policy_id)
    print("[bold]Reason[/bold]:", res.reason)
    print("[bold]Matched condition[/bold]:", res.matched)
    print("[bold]Policy order index[/bold]:", res.index)
    if parsed_args is not None:
        print("[bold]Args[/bold]:", parsed_args)


@app.command("test")
def test(
    tests: str = typer.Argument(..., help="Path to YAML test file"),
    policy: str = typer.Option("configs/policy.yaml", "--policy"),
):
    _, policy_cfg = load_and_validate(servers_path="configs/servers.yaml", policy_path=policy)

    cfg = yaml.safe_load(Path(tests).read_text(encoding="utf-8")) or {}
    fails, lines = run_policy_tests(policy_cfg, cfg)

    for line in lines:
        print(line)

    if fails:
        raise typer.Exit(code=1)
    print("[green]OK[/green]")
