"""Session management commands."""
import typer
import yaml
from datetime import datetime
from pathlib import Path
from rich.table import Table
from rich.panel import Panel
from sift.ui import console, ICONS, pipeline_view, format_next_step
from sift.models import (
    TEMPLATES_DIR, SESSIONS_DIR, ensure_dirs,
    SessionTemplate, Session, merge_templates,
)

app = typer.Typer(no_args_is_help=True)


def _find_template(name: str) -> Path:
    """Find a template by name."""
    for ext in (".yaml", ".yml"):
        path = TEMPLATES_DIR / f"{name}{ext}"
        if path.exists():
            return path
    # Try as absolute/relative path
    p = Path(name)
    if p.exists():
        return p
    raise FileNotFoundError(f"Template '{name}' not found in {TEMPLATES_DIR}")


def _parse_template_arg(template_arg: str) -> list[tuple[str, Path]]:
    """Parse a template argument that may contain '+' for multi-template.

    Returns list of (stem_name, path) tuples.
    """
    names = [t.strip() for t in template_arg.split("+")]
    results = []
    for name in names:
        path = _find_template(name)
        results.append((name, path))
    return results


@app.command("create")
def create(
    template: str = typer.Argument(..., help="Template name or path"),
    name: str = typer.Option(None, "--name", "-n", help="Session name"),
):
    """Create a new session from a template (use '+' to combine: discovery-call+workflow-extraction)."""
    ensure_dirs()

    try:
        template_specs = _parse_template_arg(template)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    if len(template_specs) == 1:
        _stem, path = template_specs[0]
        tmpl = SessionTemplate.from_file(path)
    else:
        templates = []
        stems = []
        for stem, path in template_specs:
            templates.append(SessionTemplate.from_file(path))
            stems.append(stem)
        tmpl = merge_templates(templates, stems)

    if not name:
        date_str = datetime.now().strftime("%Y-%m-%d")
        if len(template_specs) == 1:
            slug = tmpl.name.lower().replace(" ", "-")[:30]
        else:
            slug = template_specs[0][0][:20] + f"+{len(template_specs) - 1}more"
        name = f"{date_str}_{slug}"
    
    # Check if session already exists
    if (SESSIONS_DIR / name).exists():
        console.print(f"[red]Session '{name}' already exists[/red]")
        raise typer.Exit(1)
    
    session = Session.create(name, tmpl)

    # Show creation summary
    if len(template_specs) > 1:
        parts = []
        for stem, _ in template_specs:
            prefix = f"{stem}."
            tmpl_phases = [p for p in tmpl.phases if p.id.startswith(prefix)]
            parts.append(f"  [bold]{stem}[/bold]")
            for phase in tmpl_phases:
                parts.append(f"    {ICONS['pending']} {phase.name} [dim]({phase.id})[/dim]")
        phases_list = "\n".join(parts)
    else:
        phases_list = "\n".join(
            f"  {ICONS['pending']} {phase.name} [dim]({phase.id})[/dim]"
            for phase in tmpl.phases
        )

    console.print(Panel(
        f"[bold]{tmpl.name}[/bold]\n"
        f"[dim]{tmpl.description}[/dim]\n\n"
        f"{phases_list}",
        title=f"[bold green]Session Created: {name}[/bold green]",
        subtitle=f"[dim]{session.dir}[/dim]",
        border_style="green",
        padding=(1, 2),
    ))
    format_next_step(f"sift run {name}")


@app.command("list")
def list_sessions():
    """List all sessions."""
    ensure_dirs()
    
    session_dirs = [d for d in SESSIONS_DIR.iterdir() if d.is_dir() and (d / "session.yaml").exists()]
    
    if not session_dirs:
        console.print("[yellow]No sessions found.[/yellow]")
        console.print("Create one: sift new <template>")
        return
    
    table = Table(title="Sessions")
    table.add_column("Name", style="bold cyan")
    table.add_column("Template")
    table.add_column("Status")
    table.add_column("Progress")
    table.add_column("Updated")
    
    for sd in sorted(session_dirs, key=lambda d: d.stat().st_mtime, reverse=True):
        try:
            s = Session.load(sd.name)
            total = len(s.phases)
            done = sum(1 for p in s.phases.values() if p.status in ("extracted", "complete"))
            captured = sum(1 for p in s.phases.values() if p.status in ("captured", "transcribed"))
            
            progress = f"{done}/{total} done"
            if captured:
                progress += f", {captured} in progress"
            
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
                s.updated_at[:16],
            )
        except Exception as e:
            table.add_row(sd.name, "?", f"[red]Error: {e}[/red]", "-", "-")
    
    console.print(table)


@app.command("status")
def show_status(
    session: str = typer.Argument(..., help="Session name"),
):
    """Show detailed session status."""
    ensure_dirs()
    
    try:
        s = Session.load(session)
    except FileNotFoundError:
        console.print(f"[red]Session '{session}' not found[/red]")
        raise typer.Exit(1)
    
    tmpl = s.get_template()
    
    total = len(s.phases)
    done = sum(1 for p in s.phases.values() if p.status in ("extracted", "complete"))

    console.print(Panel(
        f"[bold]{s.template_name}[/bold]\n"
        f"[dim]Created: {s.created_at[:16]} | Updated: {s.updated_at[:16]}[/dim]\n"
        f"Progress: [green]{done}[/green]/{total} phases complete",
        title=f"[bold cyan]{s.name}[/bold cyan]",
        subtitle=f"Status: {s.status}",
    ))

    # Pipeline view
    phase_list = []
    for pt in tmpl.phases:
        ps = s.phases.get(pt.id)
        phase_list.append({
            "id": pt.id,
            "name": pt.name,
            "status": ps.status if ps else "pending",
        })
    pipeline_view(phase_list)

    # Detail table
    table = Table(show_header=True, border_style="dim")
    table.add_column("#", justify="center", width=3)
    table.add_column("Phase", min_width=20)
    table.add_column("Status", min_width=12)
    table.add_column("Audio", justify="center")
    table.add_column("Transcript", justify="center")
    table.add_column("Extracted", justify="center")

    for i, pt in enumerate(tmpl.phases, 1):
        ps = s.phases.get(pt.id)
        if not ps:
            continue

        icon = ICONS.get(ps.status, ICONS["pending"])
        audio = ICONS["complete"] if ps.audio_file else "[dim]\u2014[/dim]"
        transcript = ICONS["complete"] if ps.transcript_file else "[dim]\u2014[/dim]"
        extracted = ICONS["complete"] if ps.extracted_file else "[dim]\u2014[/dim]"

        table.add_row(
            str(i), f"[bold]{pt.name}[/bold]",
            f"{icon} {ps.status}", audio, transcript, extracted,
        )

    console.print(table)

    # Show next action - prioritize finishing in-progress phases first
    for pt in tmpl.phases:
        ps = s.phases.get(pt.id)
        if ps and ps.status == "transcribed":
            format_next_step(f"sift phase extract {session} --phase {pt.id}")
            return
    for pt in tmpl.phases:
        ps = s.phases.get(pt.id)
        if ps and ps.status == "captured":
            format_next_step(f"sift phase transcribe {session} --phase {pt.id}")
            return
    for pt in tmpl.phases:
        ps = s.phases.get(pt.id)
        if ps and ps.status == "pending":
            format_next_step(f"sift phase capture {session} --phase {pt.id}")
            return
    format_next_step(f"sift build generate {session}")


@app.command("export")
def export_session(
    session: str = typer.Argument(..., help="Session name"),
    output: Path = typer.Option(".", "--output", "-o", help="Output directory"),
):
    """Export all session data as a single YAML."""
    ensure_dirs()
    
    try:
        s = Session.load(session)
    except FileNotFoundError:
        console.print(f"[red]Session '{session}' not found[/red]")
        raise typer.Exit(1)
    
    tmpl = s.get_template()
    
    export = {
        "session": {
            "name": s.name,
            "template": s.template_name,
            "created_at": s.created_at,
            "status": s.status,
        },
        "phases": {},
    }
    
    for pt in tmpl.phases:
        phase_data = {"name": pt.name, "status": s.phases[pt.id].status}
        
        transcript = s.get_transcript(pt.id)
        if transcript:
            phase_data["transcript"] = transcript
        
        extracted = s.get_extracted(pt.id)
        if extracted:
            phase_data["extracted"] = extracted
        
        export["phases"][pt.id] = phase_data
    
    out_path = output / f"{session}-export.yaml"
    with open(out_path, "w") as f:
        yaml.dump(export, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    console.print(f"[green]Exported to {out_path}[/green]")
