"""Session workspace: interactive menu for browsing, editing, and rebuilding session data."""
from __future__ import annotations
import yaml
from pathlib import Path
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from rich.text import Text
from sift.ui import console, ICONS, pipeline_view, section_divider, format_next_step
from sift.models import ensure_dirs, Session
from sift.commands import phase_cmd, build_cmd
from sift import engine


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


def _show_workspace_header(session: Session, template):
    """Show the workspace header with session info and pipeline."""
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
        title=f"[bold cyan]Workspace: {session.name}[/bold cyan]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()
    pipeline_view(_build_phase_list(session, template))


def _phase_picker(session: Session, template, filter_status: list[str] = None, prompt_text: str = "Select phase") -> str:
    """Show numbered phase list and let user pick one. Returns phase_id or None."""
    eligible = []
    for i, pt in enumerate(template.phases, 1):
        ps = session.phases.get(pt.id)
        status = ps.status if ps else "pending"
        if filter_status and status not in filter_status:
            continue
        eligible.append((i, pt, status))

    if not eligible:
        console.print("  [dim]No eligible phases.[/dim]")
        return None

    for i, pt, status in eligible:
        icon = ICONS.get(status, ICONS["pending"])
        console.print(f"    [bold cyan]{i}[/bold cyan]  {icon} {pt.name} [dim]({status})[/dim]")

    console.print()
    choices = [str(i) for i, _, _ in eligible]
    choice = Prompt.ask(f"  {prompt_text}", choices=choices)
    selected = next((pt for i, pt, _ in eligible if str(i) == choice), None)
    return selected.id if selected else None


def _show_extraction_table(extracted: dict, phase_name: str):
    """Show extracted data as a Rich table."""
    if not extracted:
        console.print(f"  [dim]No extracted data for {phase_name}.[/dim]")
        return

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


# ── Action handlers ──

def _action_browse(session: Session, template):
    """Browse phase data: transcripts and extracted fields."""
    console.print("\n  [bold]Browse Phase Data[/bold]\n")
    phase_id = _phase_picker(session, template, prompt_text="View phase")
    if not phase_id:
        return

    pt = next(p for p in template.phases if p.id == phase_id)
    ps = session.phases[phase_id]

    section_divider(pt.name)

    # Show status
    console.print(f"  Status: {ICONS.get(ps.status, ICONS['pending'])} {ps.status}")
    if ps.captured_at:
        console.print(f"  Captured: [dim]{ps.captured_at[:16]}[/dim]")
    if ps.source_document:
        console.print(f"  Source: [dim]{ps.source_document} (pages {ps.source_pages})[/dim]")
    console.print()

    # Show transcript preview
    transcript = session.get_transcript(phase_id)
    if transcript:
        preview = transcript[:800]
        if len(transcript) > 800:
            preview += f"\n\n[dim]... ({len(transcript):,} total chars)[/dim]"
        console.print(Panel(
            preview,
            title="[dim]Transcript Preview[/dim]",
            border_style="dim",
        ))
    else:
        console.print("  [dim]No transcript captured yet.[/dim]")

    # Show extracted data
    extracted = session.get_extracted(phase_id)
    if extracted:
        console.print()
        _show_extraction_table(extracted, pt.name)
    else:
        console.print("\n  [dim]No extracted data yet.[/dim]")


def _action_re_extract(session_name: str, session: Session, template):
    """Re-run AI extraction on a phase."""
    console.print("\n  [bold]Re-Extract Phase[/bold]\n")

    # Only show phases that have transcripts
    phase_id = _phase_picker(
        session, template,
        filter_status=["transcribed", "extracted", "complete"],
        prompt_text="Re-extract phase",
    )
    if not phase_id:
        console.print("  [dim]No phases with transcripts available.[/dim]")
        return

    pt = next(p for p in template.phases if p.id == phase_id)

    # Show current transcript
    transcript = session.get_transcript(phase_id)
    if not transcript:
        console.print(f"  [red]No transcript for {pt.name}.[/red]")
        return

    console.print(Panel(
        transcript[:600] + ("..." if len(transcript) > 600 else ""),
        title=f"[dim]Current Transcript: {pt.name}[/dim]",
        border_style="dim",
    ))

    # Option to replace transcript
    if Confirm.ask("  Edit transcript before re-extracting?", default=False):
        console.print("\n  [bold]Enter replacement text.[/bold]")
        console.print("  [dim]Type or paste your text. Enter an empty line followed by 'END' to finish.[/dim]\n")

        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            except EOFError:
                break

        new_text = "\n".join(lines)
        if new_text.strip():
            transcript = new_text
            # Save the new transcript
            transcript_path = session.phase_dir(phase_id) / "transcript.txt"
            transcript_path.write_text(transcript)
            console.print(f"  [green]Transcript updated ({len(transcript)} chars)[/green]")
        else:
            console.print("  [dim]No text entered. Keeping original transcript.[/dim]")

    # Show existing extraction for comparison
    old_extracted = session.get_extracted(phase_id)

    if not Confirm.ask("  Run extraction now?", default=True):
        return

    # Run extraction (same logic as phase_cmd.extract_phase)
    if not pt.extract:
        console.print(f"  [yellow]{pt.name} has no extraction fields defined.[/yellow]")
        return

    # Gather context from previous phases
    context_parts = []
    for prev_pt in template.phases:
        if prev_pt.id == phase_id:
            break
        prev_data = session.get_extracted(prev_pt.id)
        if prev_data:
            context_parts.append(f"Data from '{prev_pt.name}':\n{yaml.dump(prev_data, default_flow_style=False)}")
    context = "\n\n".join(context_parts) if context_parts else ""

    extraction_fields = [{"id": e.id, "type": e.type, "prompt": e.prompt} for e in pt.extract]

    with console.status(f"[bold]Extracting {len(extraction_fields)} fields...[/bold]"):
        extracted = engine.extract_structured_data(
            transcript=transcript,
            extraction_fields=extraction_fields,
            phase_name=pt.name,
            context=context,
        )

    # Show results
    console.print()
    _show_extraction_table(extracted, f"{pt.name} (new)")

    if old_extracted:
        # Show what changed
        changes = []
        for key in set(list(extracted.keys()) + list(old_extracted.keys())):
            if key.startswith("_"):
                continue
            old_val = old_extracted.get(key)
            new_val = extracted.get(key)
            if old_val != new_val:
                changes.append(key)

        if changes:
            console.print(f"\n  [yellow]Changed fields: {', '.join(changes)}[/yellow]")
        else:
            console.print("\n  [dim]No changes from previous extraction.[/dim]")

    # Confirm save
    if Confirm.ask("  Save new extraction?", default=True):
        dest = session.phase_dir(phase_id) / "extracted.yaml"
        with open(dest, "w") as f:
            yaml.dump(extracted, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        ps = session.phases[phase_id]
        ps.extracted_file = dest.name
        ps.status = "extracted"
        from datetime import datetime
        ps.extracted_at = datetime.now().isoformat()
        session.save()
        console.print("  [green]Extraction saved.[/green]")
    else:
        console.print("  [dim]Discarded.[/dim]")


def _action_refine(session: Session, template):
    """Edit specific extracted field values."""
    console.print("\n  [bold]Refine Extracted Data[/bold]\n")

    # Only show phases with extracted data
    phase_id = _phase_picker(
        session, template,
        filter_status=["extracted", "complete"],
        prompt_text="Refine phase",
    )
    if not phase_id:
        console.print("  [dim]No phases with extracted data.[/dim]")
        return

    pt = next(p for p in template.phases if p.id == phase_id)
    extracted = session.get_extracted(phase_id)
    if not extracted:
        console.print(f"  [dim]No extracted data for {pt.name}.[/dim]")
        return

    # Show fields numbered
    fields = [(k, v) for k, v in extracted.items() if not k.startswith("_")]
    if not fields:
        console.print("  [dim]No editable fields.[/dim]")
        return

    while True:
        console.print(f"\n  [bold]{pt.name} - Fields:[/bold]\n")
        for i, (key, value) in enumerate(fields, 1):
            if isinstance(value, list):
                display = f"[dim]({len(value)} items)[/dim]"
            elif isinstance(value, dict):
                display = f"[dim]({len(value)} keys)[/dim]"
            else:
                display = str(value)[:60]
                if len(str(value)) > 60:
                    display += "..."
            console.print(f"    [bold cyan]{i}[/bold cyan]  {key}: {display}")

        console.print(f"    [bold cyan]q[/bold cyan]  Done editing")
        console.print()

        choice = Prompt.ask("  Edit field", choices=[str(i) for i in range(1, len(fields) + 1)] + ["q"])
        if choice == "q":
            break

        idx = int(choice) - 1
        key, value = fields[idx]

        console.print(f"\n  [bold]{key}[/bold] (current value):")
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    console.print("    " + ", ".join(f"{k}: {v}" for k, v in item.items()))
                else:
                    console.print(f"    \u2022 {item}")

            console.print("\n  [dim]Options: (a)dd item, (r)emove item, (c)lear all, (k)eep[/dim]")
            action = Prompt.ask("  Action", choices=["a", "r", "c", "k"], default="k")

            if action == "a":
                new_item = Prompt.ask("  New item")
                value.append(new_item)
            elif action == "r":
                for i, item in enumerate(value, 1):
                    display = str(item) if not isinstance(item, dict) else ", ".join(f"{k}: {v}" for k, v in item.items())
                    console.print(f"    {i}. {display}")
                rm_idx = Prompt.ask("  Remove #", choices=[str(i) for i in range(1, len(value) + 1)])
                value.pop(int(rm_idx) - 1)
            elif action == "c":
                value = []

        elif isinstance(value, dict):
            console.print("    " + "\n    ".join(f"{k}: {v}" for k, v in value.items()))
            console.print("\n  [dim]Options: (e)dit key, (a)dd key, (d)elete key, (k)eep[/dim]")
            action = Prompt.ask("  Action", choices=["e", "a", "d", "k"], default="k")

            if action == "e":
                edit_key = Prompt.ask("  Key to edit", choices=list(value.keys()))
                new_val = Prompt.ask(f"  New value for {edit_key}")
                value[edit_key] = new_val
            elif action == "a":
                new_key = Prompt.ask("  New key")
                new_val = Prompt.ask("  Value")
                value[new_key] = new_val
            elif action == "d":
                del_key = Prompt.ask("  Key to delete", choices=list(value.keys()))
                del value[del_key]

        else:
            console.print(f"    {value}")
            new_val = Prompt.ask("  New value (Enter to keep)", default="")
            if new_val:
                value = new_val

        # Update field
        fields[idx] = (key, value)
        extracted[key] = value

    # Save
    if Confirm.ask("  Save changes?", default=True):
        dest = session.phase_dir(phase_id) / "extracted.yaml"
        with open(dest, "w") as f:
            yaml.dump(extracted, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        session.save()
        console.print("  [green]Changes saved.[/green]")
    else:
        console.print("  [dim]Changes discarded.[/dim]")


def _action_rebuild(session_name: str, session: Session):
    """Regenerate all outputs."""
    console.print("\n  [bold]Rebuild Outputs[/bold]\n")

    try:
        build_cmd.generate(session_name, "all")
    except SystemExit:
        pass

    console.print()
    if Confirm.ask("  Generate AI summary?", default=True):
        try:
            build_cmd.ai_summary(session_name)
        except SystemExit:
            pass

    console.print("\n  [green]Rebuild complete.[/green]")


def _action_import(session_name: str):
    """Import a multi-phase document."""
    console.print("\n  [bold]Import Document[/bold]\n")

    file_path = Prompt.ask("  File path")
    path = Path(file_path.strip())

    if not path.exists():
        console.print(f"  [red]File not found: {path}[/red]")
        return

    from sift.commands.import_cmd import import_document
    try:
        import_document(session_name, path, auto=False)
    except SystemExit:
        pass


# ── Main workspace loop ──

def open_workspace(session_name: str):
    """Launch the interactive session workspace."""
    ensure_dirs()

    try:
        s = Session.load(session_name)
    except FileNotFoundError:
        console.print(f"[red]Session '{session_name}' not found[/red]")
        import typer
        raise typer.Exit(1)

    tmpl = s.get_template()

    while True:
        console.print()
        _show_workspace_header(s, tmpl)

        console.print("  What would you like to do?\n")
        console.print(f"    [bold cyan]1[/bold cyan]  Browse      [dim]View phase transcripts & extracted data[/dim]")
        console.print(f"    [bold cyan]2[/bold cyan]  Re-extract  [dim]Re-run AI extraction on a phase[/dim]")
        console.print(f"    [bold cyan]3[/bold cyan]  Refine      [dim]Edit extracted field values[/dim]")
        console.print(f"    [bold cyan]4[/bold cyan]  Rebuild     [dim]Regenerate all outputs[/dim]")
        console.print(f"    [bold cyan]5[/bold cyan]  Import      [dim]Import a multi-phase document[/dim]")
        console.print(f"    [bold cyan]q[/bold cyan]  Quit")
        console.print()

        choice = Prompt.ask("  Choose", choices=["1", "2", "3", "4", "5", "q"], default="1")

        if choice == "q":
            console.print("\n  [dim]Workspace closed.[/dim]")
            break

        # Reload session to pick up any changes
        s = Session.load(session_name)
        tmpl = s.get_template()

        if choice == "1":
            _action_browse(s, tmpl)
        elif choice == "2":
            _action_re_extract(session_name, s, tmpl)
            s = Session.load(session_name)
        elif choice == "3":
            _action_refine(s, tmpl)
            s = Session.load(session_name)
        elif choice == "4":
            _action_rebuild(session_name, s)
        elif choice == "5":
            _action_import(session_name)
            s = Session.load(session_name)

        section_divider()
