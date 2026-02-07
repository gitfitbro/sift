"""Interactive guided session runner."""
from __future__ import annotations
import typer
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.prompt import Prompt, Confirm
from sift.ui import console, ICONS, pipeline_view, step_header, section_divider, format_next_step
from sift.models import ensure_dirs, Session
from sift.commands import phase_cmd, build_cmd


def _build_phase_list(session: Session, template) -> list[dict]:
    """Build a list of phase dicts with status info for display."""
    phases = []
    for pt in template.phases:
        ps = session.phases.get(pt.id)
        phases.append({
            "id": pt.id,
            "name": pt.name,
            "status": ps.status if ps else "pending",
        })
    return phases


def _show_session_header(session: Session, template):
    """Show the session header with template info and pipeline."""
    total = len(template.phases)
    done = sum(1 for p in session.phases.values() if p.status in ("extracted", "complete"))
    in_prog = sum(1 for p in session.phases.values() if p.status in ("captured", "transcribed"))

    progress_text = f"[green]{done}[/green]/{total} complete"
    if in_prog:
        progress_text += f"  [yellow]{in_prog} in progress[/yellow]"

    content = Text.from_markup(
        f"[bold]{template.name}[/bold]\n"
        f"[dim]{template.description}[/dim]\n\n"
        f"Progress: {progress_text}"
    )

    console.print(Panel(
        content,
        title=f"[bold cyan]Session: {session.name}[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))

    console.print()
    pipeline_view(_build_phase_list(session, template))


def _show_extraction_summary(session: Session, phase_id: str, template):
    """Show a summary of extracted data for a phase."""
    extracted = session.get_extracted(phase_id)
    if not extracted:
        return

    pt = next((p for p in template.phases if p.id == phase_id), None)
    phase_name = pt.name if pt else phase_id

    table = Table(
        title=f"Extracted: {phase_name}",
        show_header=True,
        border_style="green",
        title_style="bold green",
        padding=(0, 1),
    )
    table.add_column("Field", style="bold cyan", min_width=20)
    table.add_column("Value", min_width=40)

    for field_id, value in extracted.items():
        if field_id.startswith("_"):
            continue

        if isinstance(value, list):
            if value:
                display = "\n".join(
                    f"\u2022 {item}" if not isinstance(item, dict)
                    else "\u2022 " + ", ".join(f"{k}: {v}" for k, v in item.items())
                    for item in value[:5]
                )
                if len(value) > 5:
                    display += f"\n  [dim]... and {len(value) - 5} more[/dim]"
            else:
                display = "[dim](none)[/dim]"
        elif isinstance(value, dict):
            display = "\n".join(f"{k}: {v}" for k, v in list(value.items())[:5])
            if len(value) > 5:
                display += f"\n[dim]... and {len(value) - 5} more[/dim]"
        else:
            display = str(value)[:200]
            if len(str(value)) > 200:
                display += "..."

        table.add_row(field_id.replace("_", " ").title(), display)

    console.print(table)
    console.print()


def _show_completion_summary(session: Session, template):
    """Show a final summary when all phases are done."""
    console.print()
    table = Table(
        title="Session Complete",
        show_header=True,
        border_style="green",
        title_style="bold green",
    )
    table.add_column("#", justify="center", width=3)
    table.add_column("Phase", min_width=20)
    table.add_column("Status", min_width=12)
    table.add_column("Data", min_width=15)

    for i, pt in enumerate(template.phases, 1):
        ps = session.phases.get(pt.id)
        status = ps.status if ps else "pending"
        icon = ICONS.get(status, ICONS["pending"])

        # Count extracted fields
        extracted = session.get_extracted(pt.id)
        data_info = f"[green]{len(extracted)} fields[/green]" if extracted else "[dim]--[/dim]"

        table.add_row(str(i), pt.name, f"{icon} {status}", data_info)

    console.print(table)


def run_interactive(session_name: str, start_phase: str = None):
    """Run through a session interactively, phase by phase."""
    ensure_dirs()

    try:
        s = Session.load(session_name)
    except FileNotFoundError:
        console.print(f"[error]Session '{session_name}' not found[/error]")
        raise typer.Exit(1)

    tmpl = s.get_template()

    # Show session header with pipeline
    console.print()
    _show_session_header(s, tmpl)

    # Find starting point
    phases = tmpl.phases
    if start_phase:
        idx = next((i for i, p in enumerate(phases) if p.id == start_phase), 0)
        phases = phases[idx:]
    else:
        # Start at the first incomplete phase
        for i, pt in enumerate(phases):
            ps = s.phases.get(pt.id)
            if ps and ps.status not in ("extracted", "complete"):
                phases = phases[i:]
                break

    total_phases = len(tmpl.phases)

    for i, pt in enumerate(phases):
        ps = s.phases.get(pt.id)

        # Skip completed phases
        if ps and ps.status in ("extracted", "complete"):
            console.print(f"  {ICONS['complete']} [dim]{pt.name} -- complete[/dim]")
            continue

        # Calculate step number within all phases
        step_num = next(
            (j + 1 for j, p in enumerate(tmpl.phases) if p.id == pt.id),
            i + 1,
        )

        section_divider()
        step_header(step_num, total_phases, pt.name, pt.prompt.strip())

        # Show capture options
        if pt.extract:
            fields = ", ".join(e.id for e in pt.extract)
            console.print(f"  [dim]Will extract: {fields}[/dim]\n")

        # ── Capture ──
        if ps and ps.status == "pending":
            capture_types = [c.type for c in pt.capture] if pt.capture else ["text"]

            console.print("  How do you want to capture this phase?\n")
            console.print(f"    [bold cyan]1[/bold cyan]  Upload a file [dim](audio, text, or PDF)[/dim]")
            console.print(f"    [bold cyan]2[/bold cyan]  Type or paste text directly")
            console.print(f"    [bold cyan]3[/bold cyan]  Skip for now")
            console.print()

            action = Prompt.ask(
                "  Choose",
                choices=["1", "2", "3"],
                default="1" if "audio" in capture_types else "2",
            )

            if action == "1":
                file_path = Prompt.ask("  File path")
                try:
                    from pathlib import Path
                    phase_cmd.capture_phase(session_name, pt.id, Path(file_path), False)
                except SystemExit:
                    pass
            elif action == "2":
                try:
                    phase_cmd.capture_phase(session_name, pt.id, None, True)
                except SystemExit:
                    pass
            else:
                required = any(c.required for c in pt.capture)
                if required:
                    console.print("  [warning]This phase requires capture. You can come back later.[/warning]")
                else:
                    console.print("  [muted]Skipped.[/muted]")
                continue

            # Reload session state
            s = Session.load(session_name)
            ps = s.phases.get(pt.id)

        # ── Transcribe (if audio) ──
        if ps and ps.status == "captured" and ps.audio_file:
            console.print()
            if Confirm.ask("  Transcribe audio now?", default=True):
                try:
                    phase_cmd.transcribe_phase(session_name, pt.id)
                except SystemExit:
                    pass
                s = Session.load(session_name)
                ps = s.phases.get(pt.id)

        # ── Extract ──
        if ps and ps.status == "transcribed" and pt.extract:
            console.print()
            if Confirm.ask("  Extract structured data now?", default=True):
                try:
                    phase_cmd.extract_phase(session_name, pt.id)
                except SystemExit:
                    pass
                s = Session.load(session_name)
                ps = s.phases.get(pt.id)

                # Show extraction summary
                if ps and ps.status in ("extracted", "complete"):
                    _show_extraction_summary(s, pt.id, tmpl)

        # Update pipeline view
        console.print()
        pipeline_view(_build_phase_list(s, tmpl), current_phase=pt.id)

        # Ask to continue
        remaining_phases = [
            p for p in tmpl.phases
            if s.phases[p.id].status not in ("extracted", "complete")
        ]
        if remaining_phases and i < len(phases) - 1:
            if not Confirm.ask("Continue to next phase?", default=True):
                console.print(f"\n  [dim]Session paused. Resume anytime:[/dim]")
                format_next_step(f"sift run {session_name}")
                return

    # ── Session complete ──
    section_divider()
    _show_completion_summary(s, tmpl)

    console.print()
    if Confirm.ask("Generate outputs?", default=True):
        try:
            build_cmd.generate(session_name, "all")
        except SystemExit:
            pass

    if Confirm.ask("Generate AI summary?", default=True):
        try:
            build_cmd.ai_summary(session_name)
        except SystemExit:
            pass

    console.print()
    console.print(Panel(
        "[bold green]Session complete![/bold green]",
        border_style="green",
    ))
