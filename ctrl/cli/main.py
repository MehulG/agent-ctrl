import typer
from rich import print

from ctrl.cli.policy import app as policy_app  # NEW

app = typer.Typer(help="ctrl — agent control plane (v0)")
app.add_typer(policy_app, name="policy")  # NEW

@app.command()
def version():
    print("[bold]ctrl[/bold] v0.0.1")

@app.command("validate-config")
def validate_config(
    servers: str = typer.Option("configs/servers.yaml", "--servers"),
    policy: str = typer.Option("configs/policy.yaml", "--policy"),
    db_path: str = typer.Option("ctrl.db", "--db"),
):
    from ctrl.config.loader import load_and_validate
    from ctrl.db.migrate import ensure_db

    load_and_validate(servers_path=servers, policy_path=policy)
    ensure_db(db_path=db_path)
    print("[green]OK[/green]")
    
@app.command("approvals-serve")
def approvals_serve(host: str = "127.0.0.1", port: int = 8788):
    import uvicorn
    uvicorn.run("ctrl.approvals.api:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    app()
