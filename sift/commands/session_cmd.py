"""Session management commands - thin CLI wrappers over SessionService."""

from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table

from sift.completions import complete_session_name, complete_template_name
from sift.core.session_service import SessionService
from sift.error_handler import handle_errors
from sift.ui import ICONS, console, format_next_step, pipeline_view

app = typer.Typer(no_args_is_help=True)

_svc = SessionService()


@app.command("create")
@handle_errors
def create(
    template: str = typer.Argument(
        ..., help="Template name or path", autocompletion=complete_template_name
    ),
    name: str = typer.Option(None, "--name", "-n", help="Session name"),
):
    """Create a new session from a template (use '+' to combine: discovery-call+workflow-extraction)."""
    detail = _svc.create_session(template, name)
    _render_session_created(detail)


@app.command("list")
@handle_errors
def list_sessions():
    """List all sessions."""
    sessions = _svc.list_sessions()

    if not sessions:
        console.print("[yellow]No sessions found.[/yellow]")
        console.print("Create one: sift new <template>")
        return

    table = Table(title="Sessions")
    table.add_column("Name", style="bold cyan")
    table.add_column("Template")
    table.add_column("Status")
    table.add_column("Progress")
    table.add_column("Updated")

    for s in sessions:
        progress = f"{s.done_phases}/{s.total_phases} done"
        if s.in_progress_phases:
            progress += f", {s.in_progress_phases} in progress"

        status_color = {
            "active": "yellow",
            "complete": "green",
            "archived": "dim",
        }.get(s.status, "white")

        table.add_row(
            s.name,
            s.template_name,
            f"[{status_color}]{s.status}[/{status_color}]",
            progress,
            s.updated_at[:16] if s.updated_at else "-",
        )

    console.print(table)


@app.command("status")
@handle_errors
def show_status(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
):
    """Show detailed session status."""
    detail = _svc.get_session_status(session)
    _render_session_status(detail, session)


@app.command("export")
@handle_errors
def export_session(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
    output: Path = typer.Option(".", "--output", "-o", help="Output directory"),
):
    """Export all session data as a single YAML."""
    result = _svc.export_session(session, output)
    console.print(f"[green]Exported to {result.output_path}[/green]")


# ── Render helpers ──


def _render_session_created(detail):
    """Render the session creation summary."""
    phases_list = "\n".join(
        f"  {ICONS['pending']} [bold]{p.name}[/bold] [dim]({p.id})[/dim]" for p in detail.phases
    )

    console.print(
        Panel(
            f"[bold]{detail.template_name}[/bold] "
            f"[dim]| {detail.total_phases} phases[/dim]\n\n{phases_list}",
            title=f"[bold green]Session Created: {detail.name}[/bold green]",
            border_style="green",
            padding=(1, 2),
        )
    )
    console.print()
    format_next_step(f"sift run {detail.name}")


def _render_session_status(detail, session_name: str):
    """Render detailed session status."""
    console.print(
        Panel(
            f"[bold]{detail.template_name}[/bold]\n"
            f"[dim]Created: {detail.created_at[:16]} | Updated: {detail.updated_at[:16]}[/dim]\n"
            f"Progress: [green]{detail.done_phases}[/green]/{detail.total_phases} phases complete",
            title=f"[bold cyan]{detail.name}[/bold cyan]",
            subtitle=f"Status: {detail.status}",
        )
    )

    # Pipeline view
    phase_list = [{"id": p.id, "name": p.name, "status": p.status} for p in detail.phases]
    pipeline_view(phase_list)

    # Detail table
    table = Table(show_header=True, border_style="dim")
    table.add_column("#", justify="center", width=3)
    table.add_column("Phase", min_width=20)
    table.add_column("Status", min_width=12)
    table.add_column("Audio", justify="center")
    table.add_column("Transcript", justify="center")
    table.add_column("Extracted", justify="center")

    for i, p in enumerate(detail.phases, 1):
        icon = ICONS.get(p.status, ICONS["pending"])
        audio = ICONS["complete"] if p.has_audio else "[dim]\u2014[/dim]"
        transcript = ICONS["complete"] if p.has_transcript else "[dim]\u2014[/dim]"
        extracted = ICONS["complete"] if p.has_extracted else "[dim]\u2014[/dim]"

        table.add_row(
            str(i),
            f"[bold]{p.name}[/bold]",
            f"{icon} {p.status}",
            audio,
            transcript,
            extracted,
        )

    console.print(table)

    # Show next action
    if detail.next_action:
        if detail.next_action == "build":
            cmd = f"sift build generate {session_name}"
        else:
            cmd = (
                f"sift phase {detail.next_action} {session_name} --phase {detail.next_action_phase}"
            )
        format_next_step(cmd)
