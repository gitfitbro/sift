#!/usr/bin/env python3
"""
sift: A domain-agnostic CLI for running structured sessions,
capturing audio/transcripts, extracting structured data, and generating configs.
"""
import typer
from sift.ui import console, banner
from sift.completions import (
    complete_session_name, complete_template_name,
    complete_phase_id, complete_provider_name,
)

app = typer.Typer(
    name="sift",
    help="Structured session capture & AI extraction CLI.",
    no_args_is_help=True,
    rich_markup_mode="rich",
)

# Import subcommands
from sift.commands import template_cmd, session_cmd, phase_cmd, build_cmd, import_cmd, config_cmd, doctor_cmd, plugin_cmd, export_cmd, telemetry_cmd

app.add_typer(template_cmd.app, name="template", help="Manage session templates", rich_help_panel="Advanced")
app.add_typer(session_cmd.app, name="session", help="Manage sessions", rich_help_panel="Advanced")
app.add_typer(phase_cmd.app, name="phase", help="Capture & process phase data", rich_help_panel="Advanced")
app.add_typer(build_cmd.app, name="build", help="Generate outputs from sessions", rich_help_panel="Advanced")
app.add_typer(config_cmd.app, name="config", help="Manage configuration", rich_help_panel="Advanced")
app.add_typer(doctor_cmd.app, name="doctor", help="Check environment & diagnostics", rich_help_panel="Info")
app.add_typer(plugin_cmd.app, name="plugins", help="List discovered plugins", rich_help_panel="Info")
app.add_typer(export_cmd.app, name="export", help="Export sessions & templates", rich_help_panel="Data")
app.add_typer(export_cmd.import_app, name="import-data", help="Import sessions & templates", rich_help_panel="Data")
app.add_typer(telemetry_cmd.app, name="telemetry", help="Manage anonymous telemetry", rich_help_panel="Info")


@app.callback()
def main_callback(
    provider: str = typer.Option(
        None, "--provider", "-P",
        help="AI provider to use (anthropic, gemini, ollama). Overrides AI_PROVIDER env var.",
        autocompletion=complete_provider_name,
    ),
    model: str = typer.Option(
        None, "--model", "-m",
        help="AI model to use. Overrides GEMINI_MODEL / ANTHROPIC_MODEL env var.",
    ),
    plain: bool = typer.Option(
        False, "--plain",
        help="Plain text output (no colors, no panels, ASCII). Auto-enabled when stdout is piped.",
    ),
    json_output: bool = typer.Option(
        False, "--json",
        help="Machine-readable JSON output.",
    ),
    verbose: int = typer.Option(
        0, "--verbose", "-v",
        help="Increase log verbosity (-v info, -vv debug).",
        count=True,
    ),
):
    """Structured session capture & AI extraction CLI."""
    import logging
    import sys

    # Configure logging based on verbosity
    if verbose > 0:
        log_level = {1: logging.INFO, 2: logging.DEBUG}.get(min(verbose, 2), logging.DEBUG)
        logging.basicConfig(level=log_level, format="%(name)s %(message)s")

    # Auto-detect piped output
    from sift.ui import set_plain_mode, set_json_mode
    if plain or not sys.stdout.isatty():
        set_plain_mode(True)
    if json_output:
        set_json_mode(True)
        set_plain_mode(True)  # JSON mode implies plain

    # Set model env var before provider init so it picks it up
    if model:
        import os
        provider_name = provider or os.environ.get("AI_PROVIDER", "anthropic")
        model_env = {
            "gemini": "GEMINI_MODEL",
            "anthropic": "ANTHROPIC_MODEL",
            "ollama": "OLLAMA_MODEL",
        }
        os.environ[model_env.get(provider_name, f"{provider_name.upper()}_MODEL")] = model

    if provider:
        from sift.providers import get_provider
        from sift.errors import SiftError
        try:
            p = get_provider(provider)
            if not p.is_available():
                if provider == "ollama":
                    endpoint = getattr(p, "endpoint", "http://localhost:11434")
                    console.print(
                        f"[red]Ollama server not reachable at {endpoint}.[/red]\n"
                        "[dim]Start it with: ollama serve[/dim]"
                    )
                else:
                    from sift.config import PROVIDER_KEY_MAP
                    env_var = PROVIDER_KEY_MAP.get(provider, f"{provider.upper()}_API_KEY")
                    console.print(f"[red]Provider '{provider}' requires {env_var} to be set.[/red]")
                raise typer.Exit(1)
            console.print(f"[dim]Using {provider} ({p.model})[/dim]")
        except SiftError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)


# Top-level convenience commands
@app.command(rich_help_panel="Session Workflow")
def new(
    template: str = typer.Argument(..., help="Template name or path", autocompletion=complete_template_name),
    name: str = typer.Option(None, "--name", "-n", help="Session name (auto-generated if omitted)"),
):
    """[bold cyan]Create[/bold cyan] a new session from a template."""
    banner()
    session_cmd.create(template, name)

@app.command(rich_help_panel="Session Workflow")
def run(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
    phase: str = typer.Option(None, "--phase", "-p", help="Start at specific phase", autocompletion=complete_phase_id),
    no_tui: bool = typer.Option(False, "--no-tui", help="Force Rich fallback instead of Textual TUI"),
):
    """[bold cyan]Run[/bold cyan] an interactive session (guided walkthrough)."""
    if not no_tui:
        try:
            from sift.tui.app import SiftApp
            from sift.tui.session_runner import SessionRunnerScreen
            tui = SiftApp(session)
            tui.push_screen(SessionRunnerScreen(session, start_phase=phase))
            tui.run()
            return
        except ImportError:
            pass
    banner()
    from sift.interactive import run_interactive
    run_interactive(session, phase)

@app.command(rich_help_panel="Session Workflow")
def status(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
):
    """Show session [bold]status[/bold] and progress."""
    session_cmd.show_status(session)

@app.command(rich_help_panel="Session Workflow")
def ls():
    """[bold]List[/bold] all sessions."""
    session_cmd.list_sessions()

@app.command("open", rich_help_panel="Session Workflow")
def open_session(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
    no_tui: bool = typer.Option(False, "--no-tui", help="Force Rich fallback instead of Textual TUI"),
):
    """[bold cyan]Open[/bold cyan] an interactive session workspace."""
    if not no_tui:
        try:
            from sift.tui.app import SiftApp
            from sift.tui.workspace import WorkspaceScreen
            tui = SiftApp(session)
            tui.push_screen(WorkspaceScreen(session))
            tui.run()
            return
        except ImportError:
            pass
    banner()
    from sift.commands.workspace_cmd import open_workspace
    open_workspace(session)

@app.command("import", rich_help_panel="Session Workflow")
def import_doc(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
    file: str = typer.Option(..., "--file", "-f", help="PDF or text file to import"),
):
    """[bold cyan]Import[/bold cyan] a multi-phase document into a session."""
    banner()
    from pathlib import Path
    import_cmd.import_document(session, Path(file))

@app.command(rich_help_panel="Analysis")
def analyze(
    path: str = typer.Argument(".", help="Path to project directory"),
    template: bool = typer.Option(False, "--template", "-t", help="Generate a session template recommendation"),
    save_template: bool = typer.Option(False, "--save", "-s", help="Save generated template to templates directory"),
):
    """[bold cyan]Analyze[/bold cyan] a software project's structure and architecture."""
    from pathlib import Path as P
    from rich.table import Table
    from rich.panel import Panel
    from rich.tree import Tree

    from sift.analyzers.project_analyzer import ProjectAnalyzer
    from sift.analyzers.models import ProjectStructure

    project_path = P(path).resolve()
    if not project_path.is_dir():
        console.print(f"[red]Not a directory: {project_path}[/red]")
        raise typer.Exit(1)

    # Optionally use AI provider
    provider = None
    if template:
        try:
            from sift.providers import get_provider
            provider = get_provider()
            if not provider.is_available():
                provider = None
        except Exception:
            pass

    with console.status("[bold cyan]Analyzing project...[/bold cyan]"):
        analyzer = ProjectAnalyzer()
        structure = analyzer.analyze(project_path, provider=provider)

    # Display results
    console.print()
    console.print(Panel(
        f"[bold]{structure.name}[/bold]\n"
        f"{structure.total_files} files, {structure.total_lines:,} lines",
        title="Project Analysis",
        border_style="cyan",
    ))

    # Language breakdown
    if structure.languages:
        lang_table = Table(title="Languages", show_header=True, expand=False)
        lang_table.add_column("Language", style="cyan")
        lang_table.add_column("Files", justify="right")
        for lang, count in sorted(structure.languages.items(), key=lambda x: -x[1]):
            lang_table.add_row(lang, str(count))
        console.print(lang_table)

    # Frameworks
    if structure.frameworks_detected:
        console.print(f"\n[bold]Frameworks:[/bold] {', '.join(structure.frameworks_detected)}")

    # Entry points
    if structure.entry_points:
        console.print(f"[bold]Entry points:[/bold] {', '.join(structure.entry_points[:5])}")

    # Dependencies summary
    if structure.dependencies:
        console.print(f"[bold]Dependencies:[/bold] {len(structure.dependencies)} detected")

    # Directory tree
    if structure.directory_tree:
        console.print(Panel(structure.directory_tree, title="Directory Structure", border_style="dim"))

    # Architecture summary (AI-generated)
    if structure.architecture_summary:
        console.print(Panel(
            structure.architecture_summary,
            title="Architecture Summary (AI)",
            border_style="green",
        ))

    # Top complexity files
    top_complex = sorted(
        [f for f in structure.file_analyses if f.complexity_score > 0],
        key=lambda f: f.complexity_score,
        reverse=True,
    )[:5]
    if top_complex:
        cx_table = Table(title="Complexity Hotspots", show_header=True, expand=False)
        cx_table.add_column("File", style="yellow")
        cx_table.add_column("Lines", justify="right")
        cx_table.add_column("Functions", justify="right")
        cx_table.add_column("Complexity", justify="right", style="red")
        for fa in top_complex:
            try:
                rel = str(fa.path.relative_to(project_path))
            except ValueError:
                rel = str(fa.path)
            cx_table.add_row(rel, str(fa.line_count), str(len(fa.functions)), f"{fa.complexity_score:.1f}")
        console.print(cx_table)

    # Template recommendation
    if template:
        console.print()
        rec = analyzer.recommend_template(structure, provider=provider)
        console.print(Panel(
            f"[bold]{rec.template_name}[/bold]\n{rec.description}\n\n"
            f"[dim]{rec.rationale}[/dim]",
            title="Template Recommendation",
            border_style="magenta",
        ))

        phase_table = Table(title="Recommended Phases", show_header=True, expand=False)
        phase_table.add_column("#", justify="right", style="dim")
        phase_table.add_column("Phase", style="cyan")
        phase_table.add_column("Prompt")
        for i, phase in enumerate(rec.phases, 1):
            phase_table.add_row(
                str(i),
                phase.get("name", phase.get("id", "?")),
                (phase.get("prompt", "")[:80] + "...") if len(phase.get("prompt", "")) > 80 else phase.get("prompt", ""),
            )
        console.print(phase_table)

        if save_template:
            import yaml
            from sift.models import TEMPLATES_DIR
            TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
            template_path = TEMPLATES_DIR / f"{rec.template_name}.yaml"
            template_data = {
                "name": rec.template_name,
                "description": rec.description,
                "phases": rec.phases,
                "outputs": [
                    {"type": "yaml", "template": "session-config"},
                    {"type": "markdown", "template": "session-summary"},
                ],
            }
            with open(template_path, "w") as f:
                yaml.dump(template_data, f, default_flow_style=False, sort_keys=False)
            console.print(f"\n[green]Template saved to:[/green] {template_path}")


@app.command(rich_help_panel="Info")
def models(
    provider_filter: str = typer.Option(
        None, "--provider", "-P",
        help="Show models for a specific provider only",
        autocompletion=complete_provider_name,
    ),
):
    """List available AI models for each provider."""
    from rich.table import Table
    import os

    from sift.core.config_service import get_config_service

    config = get_config_service()
    active_provider = config.get_provider_name()

    table = Table(title="Available Models", show_header=True)
    table.add_column("Provider", style="cyan")
    table.add_column("Model ID", style="bold")
    table.add_column("Description")
    table.add_column("Active", justify="center")

    # Anthropic models
    if not provider_filter or provider_filter == "anthropic":
        active_model = config.get_provider_model("anthropic")
        anthropic_models = {
            "claude-sonnet-4-5-20250514": "Fast, intelligent (default)",
            "claude-opus-4-20250514": "Most capable, complex tasks",
            "claude-haiku-3-5-20241022": "Fastest, lowest cost",
        }
        for model_id, desc in anthropic_models.items():
            active = "*" if active_provider == "anthropic" and model_id == active_model else ""
            table.add_row("anthropic", model_id, desc, active)

    # Gemini models
    if not provider_filter or provider_filter == "gemini":
        from sift.providers.gemini_provider import GEMINI_MODELS
        active_model = config.get_provider_model("gemini")
        for model_id, desc in GEMINI_MODELS.items():
            active = "*" if active_provider == "gemini" and model_id == active_model else ""
            table.add_row("gemini", model_id, desc, active)

    # Ollama models
    if not provider_filter or provider_filter == "ollama":
        from sift.providers.ollama_provider import OLLAMA_MODELS
        active_model = config.get_provider_model("ollama")
        try:
            from sift.providers.ollama_provider import OllamaProvider
            ollama = OllamaProvider()
            server_models = ollama.list_models()
            if server_models:
                for m in server_models:
                    model_name = m.get("name", m.get("model", "unknown"))
                    size = m.get("size", 0)
                    size_str = f" ({size / (1024**3):.1f}GB)" if size else ""
                    active = "*" if active_provider == "ollama" and model_name == active_model else ""
                    table.add_row("ollama", model_name, f"Local{size_str}", active)
            else:
                for model_id, desc in OLLAMA_MODELS.items():
                    active = "*" if active_provider == "ollama" and model_id == active_model else ""
                    table.add_row("ollama", model_id, f"{desc} (not pulled)", active)
        except Exception:
            for model_id, desc in OLLAMA_MODELS.items():
                active = "*" if active_provider == "ollama" and model_id == active_model else ""
                table.add_row("ollama", model_id, f"{desc} (server offline)", active)

    console.print(table)
    console.print()
    console.print("[dim]Switch provider:[/dim]  sift --provider ollama --model llama3.2 run my-session")
    console.print("[dim]Set default:[/dim]     sift config set providers.default ollama")


if __name__ == "__main__":
    app()
