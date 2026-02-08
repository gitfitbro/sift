"""Build commands: generate outputs from completed sessions - thin CLI wrappers."""
import typer
from rich.panel import Panel
from sift.ui import console
from sift.core.build_service import BuildService
from sift.completions import complete_session_name, complete_format

app = typer.Typer(no_args_is_help=True)

_svc = BuildService()


@app.command("generate")
def generate(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
    format: str = typer.Option("all", "--format", "-f", help="Output format: yaml, markdown, all", autocompletion=complete_format),
):
    """Generate outputs from a session's extracted data."""
    try:
        result = _svc.generate_outputs(session, format)
    except FileNotFoundError:
        console.print(f"[red]Session '{session}' not found[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(1)

    console.print(f"\n[green bold]Outputs generated:[/green bold]\n")
    for label, path in result.generated_files:
        console.print(f"  [bold]{label}[/bold]: {path}")

    console.print(f"\n[dim]All outputs in: {result.output_dir}[/dim]")


@app.command("summary")
def ai_summary(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
):
    """Generate an AI-powered narrative summary of the session."""
    try:
        with console.status("[bold]Generating AI summary...[/bold]"):
            summary, summary_path = _svc.generate_summary(session)
    except FileNotFoundError:
        console.print(f"[red]Session '{session}' not found[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[yellow]{e}[/yellow]")
        raise typer.Exit(1)

    console.print(Panel(summary, title="AI Summary", border_style="green"))
    console.print(f"\n[dim]Saved to: {summary_path}[/dim]")
