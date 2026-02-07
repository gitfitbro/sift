#!/usr/bin/env python3
"""
sift: A domain-agnostic CLI for running structured sessions,
capturing audio/transcripts, extracting structured data, and generating configs.
"""
import typer
from sift.ui import console, banner

app = typer.Typer(
    name="sift",
    help="Structured session capture & AI extraction CLI.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Import subcommands
from sift.commands import template_cmd, session_cmd, phase_cmd, build_cmd, import_cmd

app.add_typer(template_cmd.app, name="template", help="Manage session templates", rich_help_panel="Advanced")
app.add_typer(session_cmd.app, name="session", help="Manage sessions", rich_help_panel="Advanced")
app.add_typer(phase_cmd.app, name="phase", help="Capture & process phase data", rich_help_panel="Advanced")
app.add_typer(build_cmd.app, name="build", help="Generate outputs from sessions", rich_help_panel="Advanced")


@app.callback()
def main_callback(
    provider: str = typer.Option(
        None, "--provider", "-P",
        help="AI provider to use (anthropic, gemini). Overrides AI_PROVIDER env var.",
    ),
    model: str = typer.Option(
        None, "--model", "-m",
        help="AI model to use. Overrides GEMINI_MODEL / ANTHROPIC_MODEL env var.",
    ),
):
    """Structured session capture & AI extraction CLI."""
    # Set model env var before provider init so it picks it up
    if model:
        import os
        provider_name = provider or os.environ.get("AI_PROVIDER", "anthropic")
        if provider_name == "gemini":
            os.environ["GEMINI_MODEL"] = model
        else:
            os.environ["ANTHROPIC_MODEL"] = model

    if provider:
        from sift.providers import get_provider
        try:
            p = get_provider(provider)
            if not p.is_available():
                from sift.config import PROVIDER_KEY_MAP
                env_var = PROVIDER_KEY_MAP.get(provider, f"{provider.upper()}_API_KEY")
                console.print(f"[red]Provider '{provider}' requires {env_var} to be set.[/red]")
                raise typer.Exit(1)
            console.print(f"[dim]Using {provider} ({p.model})[/dim]")
        except ValueError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)


# Top-level convenience commands
@app.command(rich_help_panel="Session Workflow")
def new(
    template: str = typer.Argument(..., help="Template name or path"),
    name: str = typer.Option(None, "--name", "-n", help="Session name (auto-generated if omitted)"),
):
    """[bold cyan]Create[/bold cyan] a new session from a template."""
    banner()
    session_cmd.create(template, name)

@app.command(rich_help_panel="Session Workflow")
def run(
    session: str = typer.Argument(..., help="Session name"),
    phase: str = typer.Option(None, "--phase", "-p", help="Start at specific phase"),
):
    """[bold cyan]Run[/bold cyan] an interactive session (guided walkthrough)."""
    banner()
    from sift.interactive import run_interactive
    run_interactive(session, phase)

@app.command(rich_help_panel="Session Workflow")
def status(
    session: str = typer.Argument(..., help="Session name"),
):
    """Show session [bold]status[/bold] and progress."""
    session_cmd.show_status(session)

@app.command(rich_help_panel="Session Workflow")
def ls():
    """[bold]List[/bold] all sessions."""
    session_cmd.list_sessions()

@app.command("open", rich_help_panel="Session Workflow")
def open_session(
    session: str = typer.Argument(..., help="Session name"),
):
    """[bold cyan]Open[/bold cyan] an interactive session workspace."""
    banner()
    from sift.commands.workspace_cmd import open_workspace
    open_workspace(session)

@app.command("import", rich_help_panel="Session Workflow")
def import_doc(
    session: str = typer.Argument(..., help="Session name"),
    file: str = typer.Option(..., "--file", "-f", help="PDF or text file to import"),
):
    """[bold cyan]Import[/bold cyan] a multi-phase document into a session."""
    banner()
    from pathlib import Path
    import_cmd.import_document(session, Path(file))

@app.command(rich_help_panel="Info")
def models():
    """List available AI models for each provider."""
    from rich.table import Table

    from sift.providers.gemini_provider import GEMINI_MODELS

    current_provider = typer.Context
    import os
    active_provider = os.environ.get("AI_PROVIDER", "anthropic")
    active_gemini_model = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")
    active_anthropic_model = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-5-20250514")

    table = Table(title="Available Models", show_header=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Model ID", style="bold")
    table.add_column("Description")
    table.add_column("Active", justify="center")

    # Gemini models
    for model_id, desc in GEMINI_MODELS.items():
        active = "*" if active_provider == "gemini" and model_id == active_gemini_model else ""
        table.add_row("gemini", model_id, desc, active)

    # Anthropic models
    anthropic_models = {
        "claude-sonnet-4-5-20250514": "Fast, intelligent (default)",
        "claude-opus-4-20250514": "Most capable, complex tasks",
        "claude-haiku-3-5-20241022": "Fastest, lowest cost",
    }
    for model_id, desc in anthropic_models.items():
        active = "*" if active_provider == "anthropic" and model_id == active_anthropic_model else ""
        table.add_row("anthropic", model_id, desc, active)

    console.print(table)
    console.print()
    console.print("[dim]Switch model:[/dim]  sift --model gemini-2.5-pro-preview-05-06 run my-session")
    console.print("[dim]Set default:[/dim]   GEMINI_MODEL=gemini-2.5-pro-preview-05-06  (in .env)")


if __name__ == "__main__":
    app()
