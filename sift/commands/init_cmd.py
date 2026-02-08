"""Init command - first-time setup wizard for sift.

Validates environment, configures an AI provider, and guides the user
through their first session.
"""

from __future__ import annotations

import sys

import typer

from sift.error_handler import handle_errors
from sift.ui import ICONS, console

app = typer.Typer(no_args_is_help=False)


@app.callback(invoke_without_command=True)
@handle_errors
def init() -> None:
    """Set up sift for the first time (validate env, configure provider, run checks)."""
    from rich.panel import Panel
    from rich.table import Table

    console.print(
        Panel(
            "[bold cyan]  s i f t[/bold cyan]\n[dim]  First-time setup wizard[/dim]",
            border_style="cyan",
            padding=(0, 4),
        )
    )

    checks: list[tuple[str, bool, str]] = []

    # 1. Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    checks.append(
        ("Python version", py_ok, f"{py_version} {'(OK)' if py_ok else '(requires 3.10+)'}")
    )

    if not py_ok:
        console.print(
            "[red]Python 3.10+ is required. Please upgrade your Python installation.[/red]"
        )
        raise typer.Exit(1)

    # 2. Data directories
    from sift.models import SESSIONS_DIR, TEMPLATES_DIR, ensure_dirs

    ensure_dirs()
    checks.append(("Data directories", True, f"Templates: {TEMPLATES_DIR}"))
    checks.append(("", True, f"Sessions: {SESSIONS_DIR}"))

    # 3. Templates check
    template_count = len(list(TEMPLATES_DIR.glob("*.yaml"))) + len(
        list(TEMPLATES_DIR.glob("*.yml"))
    )
    if template_count == 0:
        _install_default_templates()
        template_count = len(list(TEMPLATES_DIR.glob("*.yaml"))) + len(
            list(TEMPLATES_DIR.glob("*.yml"))
        )
    checks.append(("Templates installed", template_count > 0, f"{template_count} templates"))

    # 4. Provider configuration
    from sift.core.secrets import list_stored_providers

    key_status = list_stored_providers()
    has_any_key = any(s in ("env", "keyring", "file", "no key needed") for s in key_status.values())

    for provider_name, status in key_status.items():
        has_key = status in ("env", "keyring", "file", "no key needed")
        checks.append((f"Provider: {provider_name}", has_key, f"API key: {status}"))

    # Display checks
    console.print()
    table = Table(title="Environment Check", show_header=True, border_style="cyan")
    table.add_column("Check", min_width=22)
    table.add_column("Status", justify="center", width=6)
    table.add_column("Detail")

    for name, passed, detail in checks:
        if not name:
            table.add_row("", "", detail)
            continue
        icon = ICONS["complete"] if passed else ICONS["error"]
        table.add_row(name, icon, detail)

    console.print(table)

    # 5. Offer to configure a provider if none available
    if not has_any_key:
        console.print(
            "\n[yellow]No AI provider configured.[/yellow] "
            "sift needs an API key for transcription and extraction.\n"
        )

        configure = typer.confirm("Would you like to configure a provider now?", default=True)
        if configure:
            _configure_provider()
    else:
        console.print("\n[green]Environment looks good![/green]")

    # 6. Show next steps
    console.print(
        Panel(
            "[bold]Try these next:[/bold]\n\n"
            "  [cyan]sift demo[/cyan]                              "
            "See sift in action (no API key needed)\n"
            "  [cyan]sift new hello-world --name my-first[/cyan]   "
            "Create your first real session\n"
            "  [cyan]sift template list[/cyan]                     "
            "Browse available templates\n"
            "  [cyan]sift doctor[/cyan]                            "
            "Run full diagnostics",
            title="[bold cyan]What's next?[/bold cyan]",
            border_style="cyan",
            padding=(0, 2),
        )
    )


def _install_default_templates() -> None:
    """Copy built-in templates to the user's template directory."""
    import shutil
    from pathlib import Path

    from sift.models import TEMPLATES_DIR

    # Find the package templates directory
    package_dir = Path(__file__).parent.parent.parent / "templates"
    if not package_dir.exists():
        # Try as installed package
        import importlib.resources

        try:
            with importlib.resources.path("sift", "__init__") as p:
                package_dir = p.parent.parent / "templates"
        except Exception:
            console.print("[dim]Could not locate built-in templates.[/dim]")
            return

    if not package_dir.exists():
        return

    count = 0
    for template_file in package_dir.glob("*.yaml"):
        dest = TEMPLATES_DIR / template_file.name
        if not dest.exists():
            shutil.copy2(template_file, dest)
            count += 1

    if count > 0:
        console.print(f"[dim]Installed {count} default templates.[/dim]")


def _configure_provider() -> None:
    """Interactive provider configuration."""
    from sift.core.secrets import store_key

    console.print("[bold]Choose a provider:[/bold]")
    console.print("  1. [cyan]Anthropic[/cyan] (Claude) - Recommended")
    console.print("  2. [cyan]Google Gemini[/cyan]")
    console.print("  3. [cyan]Ollama[/cyan] (Local, no API key needed)")
    console.print()

    choice = typer.prompt("Enter choice (1-3)", default="1")

    provider_map = {"1": "anthropic", "2": "gemini", "3": "ollama"}
    provider = provider_map.get(choice, "anthropic")

    if provider == "ollama":
        from sift.core.config_service import get_config_service

        svc = get_config_service()
        svc.set_global("providers.default", "ollama")
        console.print(
            "[green]Ollama configured as default provider.[/green]\n"
            "[dim]Make sure Ollama is running: ollama serve[/dim]"
        )
        return

    env_var_map = {"anthropic": "ANTHROPIC_API_KEY", "gemini": "GOOGLE_API_KEY"}
    env_var = env_var_map[provider]

    console.print(f"\nEnter your {provider} API key.")
    console.print(f"[dim](This will be stored securely. You can also set {env_var} instead.)[/dim]")

    api_key = typer.prompt("API key", hide_input=True)
    if not api_key.strip():
        console.print("[yellow]No key entered. Skipping provider configuration.[/yellow]")
        return

    store_key(provider, api_key.strip())

    from sift.core.config_service import get_config_service

    svc = get_config_service()
    svc.set_global("providers.default", provider)

    console.print(f"\n[green]Configured {provider} as default provider.[/green]")
