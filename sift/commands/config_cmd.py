"""CLI commands for configuration management."""
from __future__ import annotations

import typer
from sift.ui import console
from sift.error_handler import handle_errors

app = typer.Typer(
    name="config",
    help="Manage sift configuration.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)


@app.command()
@handle_errors
def show():
    """Display the resolved configuration (all layers merged)."""
    from rich.panel import Panel
    from rich.table import Table
    from sift.core.config_service import get_config_service

    svc = get_config_service()
    info = svc.show()

    # Sources
    sources = info["sources"]
    console.print(Panel(
        f"Global:  {sources['global_config'] or '[dim]not found[/dim]'}\n"
        f"Project: {sources['project_config'] or '[dim]not found[/dim]'}",
        title="Config Sources",
        border_style="cyan",
    ))

    # Resolved values
    resolved = info["resolved"]

    # Providers section
    providers = resolved.get("providers", {})
    table = Table(title="Providers", show_header=True)
    table.add_column("Setting", style="cyan")
    table.add_column("Value")
    table.add_row("default", str(providers.get("default", "")))
    for name in ("anthropic", "gemini", "ollama"):
        prov = providers.get(name, {})
        if isinstance(prov, dict):
            for key, val in prov.items():
                table.add_row(f"{name}.{key}", str(val))
    console.print(table)

    # Session section
    session_cfg = resolved.get("session", {})
    if session_cfg:
        table2 = Table(title="Session", show_header=True)
        table2.add_column("Setting", style="cyan")
        table2.add_column("Value")
        for key, val in session_cfg.items():
            table2.add_row(key, str(val) if val else "[dim]not set[/dim]")
        console.print(table2)

    # Key status
    from sift.core.secrets import list_stored_providers
    key_status = list_stored_providers()
    table3 = Table(title="API Keys", show_header=True)
    table3.add_column("Provider", style="cyan")
    table3.add_column("Status")
    for provider, status in key_status.items():
        style = "green" if status in ("env", "keyring", "file") else "dim"
        table3.add_row(provider, f"[{style}]{status}[/{style}]")
    console.print(table3)


@app.command("set")
@handle_errors
def set_value(
    key: str = typer.Argument(..., help="Config key in dotted notation (e.g. providers.default)"),
    value: str = typer.Argument(..., help="Value to set"),
):
    """Set a global configuration value."""
    from sift.core.config_service import get_config_service

    svc = get_config_service()

    # Convert string booleans
    parsed_value: object
    if value.lower() in ("true", "yes", "1"):
        parsed_value = True
    elif value.lower() in ("false", "no", "0"):
        parsed_value = False
    else:
        try:
            parsed_value = int(value)
        except ValueError:
            parsed_value = value

    svc.set_global(key, parsed_value)
    console.print(f"[green]Set[/green] {key} = {parsed_value}")


@app.command("set-key")
@handle_errors
def set_key(
    provider: str = typer.Argument(..., help="Provider name (anthropic, gemini)"),
    api_key: str = typer.Argument(..., help="API key to store"),
):
    """Store an API key securely for a provider."""
    from sift.core.secrets import store_key

    store_key(provider, api_key)
    console.print(f"[green]Stored API key for {provider}[/green]")


@app.command("remove-key")
@handle_errors
def remove_key(
    provider: str = typer.Argument(..., help="Provider name (anthropic, gemini)"),
):
    """Remove a stored API key for a provider."""
    from sift.core.secrets import remove_key as _remove_key

    removed = _remove_key(provider)
    if removed:
        console.print(f"[green]Removed API key for {provider}[/green]")
    else:
        console.print(f"[yellow]No stored key found for {provider}[/yellow]")


@app.command()
@handle_errors
def init():
    """Create a .sift.toml project config in the current directory."""
    from sift.core.config_service import get_config_service

    svc = get_config_service()
    path = svc.init_project_config()
    console.print(f"[green]Created project config:[/green] {path}")


@app.command()
@handle_errors
def path():
    """Show all configuration file locations."""
    from rich.table import Table
    from sift.core.config_service import get_config_service

    svc = get_config_service()
    paths = svc.config_paths()

    table = Table(title="Config Paths", show_header=True)
    table.add_column("File", style="cyan")
    table.add_column("Location")
    for name, location in paths.items():
        table.add_row(name, location)
    console.print(table)
