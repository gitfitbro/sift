"""Diagnostic command: check environment setup and provider health."""
from __future__ import annotations

import logging
import sys

import typer
from rich.table import Table

from sift.ui import console, ICONS

app = typer.Typer(no_args_is_help=False)
logger = logging.getLogger("sift.doctor")


@app.callback(invoke_without_command=True)
def doctor(
    verbose: bool = typer.Option(False, "--verbose", "-v", help="Show detailed diagnostics"),
):
    """Run diagnostic checks on sift environment."""
    checks: list[tuple[str, bool, str]] = []

    # 1. Python version
    py_version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    checks.append(("Python version", py_ok, f"{py_version} {'(OK)' if py_ok else '(requires 3.10+)'}"))

    # 2. Data directory
    from sift.core.config_service import get_config_service
    config_svc = get_config_service()
    data_dir = config_svc.get_data_dir()
    data_ok = data_dir.exists()
    checks.append(("Data directory", data_ok, f"{data_dir} {'(exists)' if data_ok else '(not found)'}"))

    # 3. Templates directory
    templates_dir = data_dir / "templates"
    tmpl_ok = templates_dir.exists()
    tmpl_count = 0
    if tmpl_ok:
        tmpl_count = len(list(templates_dir.glob("*.yaml"))) + len(list(templates_dir.glob("*.yml")))
    checks.append((
        "Templates",
        tmpl_ok,
        f"{tmpl_count} templates in {templates_dir}" if tmpl_ok else f"{templates_dir} not found",
    ))

    # 4. Sessions directory
    sessions_dir = data_dir / "sessions"
    sess_ok = sessions_dir.exists()
    checks.append(("Sessions directory", sess_ok, str(sessions_dir)))

    # 5. Provider availability
    from sift.core.secrets import list_stored_providers
    key_status = list_stored_providers()
    for provider_name, status in key_status.items():
        has_key = status in ("env", "keyring", "file", "no key needed")
        detail = f"API key: {status}"
        if has_key and verbose:
            try:
                from sift.providers import PROVIDERS, _register_defaults
                _register_defaults()
                if provider_name in PROVIDERS:
                    p = PROVIDERS[provider_name]()
                    detail += f" | model: {p.model}"
                    if provider_name == "ollama":
                        if p.is_available():
                            detail += f" | server: reachable ({p.endpoint})"
                        else:
                            detail += f" | server: not reachable ({p.endpoint})"
                            has_key = False
            except Exception as e:
                detail += f" | init error: {e}"
        checks.append((f"Provider: {provider_name}", has_key, detail))

    # 6. Optional dependencies
    optional_deps = [
        ("pdfplumber", "PDF support"),
        ("whisper", "Local transcription"),
        ("keyring", "Secure key storage"),
        ("textual", "TUI interface"),
        ("anthropic", "Anthropic SDK"),
        ("google.genai", "Gemini SDK"),
    ]
    for module_name, description in optional_deps:
        try:
            __import__(module_name)
            dep_ok = True
        except ImportError:
            dep_ok = False
        checks.append((
            f"Optional: {description}",
            dep_ok,
            f"{module_name} {'installed' if dep_ok else 'not installed'}",
        ))

    # 7. Config file validity
    paths = config_svc.config_paths()
    for config_name, config_detail in paths.items():
        exists = "exists" in config_detail
        checks.append((f"Config: {config_name}", exists or config_name == "project_config", config_detail))

    # Render results
    table = Table(title="sift doctor", show_header=True, border_style="cyan")
    table.add_column("Check", min_width=25)
    table.add_column("Status", justify="center", width=6)
    table.add_column("Detail")

    all_ok = True
    for name, passed, detail in checks:
        icon = ICONS["complete"] if passed else ICONS["error"]
        table.add_row(name, icon, detail)
        # Optional deps and project config are not required
        if not passed and not name.startswith("Optional:") and not name.startswith("Config: project"):
            all_ok = False

    console.print(table)

    if all_ok:
        console.print("\n[green]All checks passed.[/green]")
    else:
        console.print("\n[yellow]Some checks failed. See details above.[/yellow]")
        raise typer.Exit(1)
