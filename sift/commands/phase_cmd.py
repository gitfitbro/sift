"""Phase-level commands: capture, transcribe, extract - thin CLI wrappers."""

from pathlib import Path

import typer
from rich.panel import Panel
from rich.table import Table as RichTable

from sift.completions import complete_phase_id, complete_session_name
from sift.core.extraction_service import ExtractionService
from sift.error_handler import handle_errors
from sift.pdf import PDF_ENGINE
from sift.ui import console, format_next_step

app = typer.Typer(no_args_is_help=True)

_svc = ExtractionService()


def _phase_has_content(session: str, phase: str) -> bool:
    """Check if a phase already has a transcript."""
    from sift.models import Session

    try:
        s = Session.load(session)
        ps = s.phases.get(phase)
        return bool(ps and ps.status not in ("pending",))
    except Exception:
        return False


def _ask_append_or_replace() -> str:
    """Ask user whether to append, replace, or cancel."""
    console.print("\n[yellow]This phase already has content.[/yellow]\n")
    console.print("  [bold]1[/bold]. Append more content")
    console.print("  [bold]2[/bold]. Replace existing content")
    console.print("  [bold]3[/bold]. Cancel")
    console.print()
    choice = typer.prompt("Choice", type=int, default=1)
    if choice == 1:
        return "append"
    elif choice == 2:
        return "replace"
    return "cancel"


def _read_text_input() -> str:
    """Read multi-line text from stdin until END or Ctrl+C/EOF."""
    console.print("\n[bold]Enter transcript text.[/bold]")
    console.print(
        "[dim]Type or paste your text. Enter an empty line followed by 'END' to finish.[/dim]\n"
    )
    lines = []
    while True:
        try:
            line = input()
            if line.strip() == "END":
                break
            lines.append(line)
        except (EOFError, KeyboardInterrupt):
            console.print()
            break
    return "\n".join(lines)


@app.command("capture")
@handle_errors
def capture_phase(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
    phase: str = typer.Option(
        ..., "--phase", "-p", help="Phase ID", autocompletion=complete_phase_id
    ),
    file: Path = typer.Option(None, "--file", "-f", help="Upload audio/transcript/PDF file"),
    text: bool = typer.Option(False, "--text", "-t", help="Enter text directly"),
    append: bool = typer.Option(False, "--append", "-a", help="Append to existing content"),
    replace: bool = typer.Option(False, "--replace", help="Replace existing content"),
):
    """Capture audio, transcript, or PDF document for a session phase."""
    has_content = _phase_has_content(session, phase)

    # Determine append mode for direct flags (--file or --text)
    if has_content and (file or text) and not append and not replace:
        action = _ask_append_or_replace()
        if action == "cancel":
            console.print("[dim]Cancelled.[/dim]")
            return
        append = action == "append"

    if file:
        result = _svc.capture_file(session, phase, file, append=append)
        _render_capture_result(result, file, session, phase)

        # If multi-phase detected, suggest import command
        if result.multi_phase_detected:
            console.print(
                Panel(
                    "[yellow]This document appears to contain content for multiple phases.[/yellow]\n"
                    f"Consider using: [bold cyan]sift import {session} --file {file}[/bold cyan]\n"
                    "This will analyze the document and distribute sections to the right phases automatically.",
                    title="Multi-Phase Document Detected",
                    border_style="yellow",
                )
            )

    elif text:
        transcript = _read_text_input()
        if not transcript.strip():
            console.print("[yellow]No text entered. Aborting.[/yellow]")
            raise typer.Exit(0)

        result = _svc.capture_text(session, phase, transcript, append=append)
        label = "appended to transcript" if result.appended else "Transcript saved"
        console.print(f"\n[green]{label} ({result.char_count} chars)[/green]")
        format_next_step(f"sift phase extract {session} --phase {phase}")

    else:
        # Interactive mode — ask what to do
        if has_content:
            action = _ask_append_or_replace()
            if action == "cancel":
                console.print("[dim]Cancelled.[/dim]")
                return
            append = action == "append"

        console.print("\nHow would you like to capture this phase?\n")
        console.print("  [bold]1[/bold]. Upload a file (audio, transcript, or PDF)")
        console.print("  [bold]2[/bold]. Enter/paste text directly")
        console.print("  [bold]3[/bold]. Skip for now")
        console.print()

        choice = typer.prompt("Choice", type=int, default=1)

        if choice == 1:
            file_path = typer.prompt("File path")
            result = _svc.capture_file(session, phase, Path(file_path), append=append)
            _render_capture_result(result, Path(file_path), session, phase)
        elif choice == 2:
            transcript = _read_text_input()
            if not transcript.strip():
                console.print("[yellow]No text entered. Aborting.[/yellow]")
                return
            result = _svc.capture_text(session, phase, transcript, append=append)
            label = "appended to transcript" if result.appended else "Transcript saved"
            console.print(f"\n[green]{label} ({result.char_count} chars)[/green]")
            format_next_step(f"sift phase extract {session} --phase {phase}")
        else:
            console.print("[dim]Skipping...[/dim]")


@app.command("transcribe")
@handle_errors
def transcribe_phase(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
    phase: str = typer.Option(
        ..., "--phase", "-p", help="Phase ID", autocompletion=complete_phase_id
    ),
):
    """Transcribe audio for a session phase."""
    result = _svc.transcribe_phase(session, phase)

    console.print(f"\n[green]Transcription complete ({result.char_count} chars)[/green]")
    console.print(
        Panel(
            result.transcript_preview,
            title="Transcript Preview",
            border_style="dim",
        )
    )
    format_next_step(f"sift phase extract {session} --phase {phase}")


@app.command("extract")
@handle_errors
def extract_phase(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
    phase: str = typer.Option(
        ..., "--phase", "-p", help="Phase ID", autocompletion=complete_phase_id
    ),
):
    """Extract structured data from a phase transcript."""
    with console.status("[bold]Extracting structured data...[/bold]"):
        result = _svc.extract_phase(session, phase)

    if not result.fields:
        console.print(
            f"[yellow]Phase '{phase}' has no extraction fields defined. Marked complete.[/yellow]"
        )
        return

    console.print("\n[green]Extraction complete[/green]\n")
    _render_extracted_fields(result.fields)

    # Suggest next action
    remaining = _svc.get_remaining_phases(session)
    if remaining:
        next_p = remaining[0]
        status = next_p["status"]
        pid = next_p["phase_id"]
        if status == "pending":
            format_next_step(f"sift phase capture {session} --phase {pid}")
        elif status == "captured":
            format_next_step(f"sift phase transcribe {session} --phase {pid}")
        else:
            format_next_step(f"sift phase extract {session} --phase {pid}")
    else:
        console.print("\n  [bold green]All phases complete![/bold green]")
        format_next_step(f"sift build generate {session}")


# ── Render helpers ──


def _render_capture_result(result, file: Path, session: str, phase: str):
    """Render capture result based on file type."""
    if result.file_type == "audio":
        console.print("[green]Audio uploaded[/green]")
        format_next_step(f"sift phase transcribe {session} --phase {phase}")

    elif result.file_type == "text":
        console.print("[green]Transcript uploaded[/green]")
        format_next_step(f"sift phase extract {session} --phase {phase}")

    elif result.file_type == "pdf" and result.pdf_stats:
        stats_table = RichTable(show_header=False, box=None, padding=(0, 2))
        stats_table.add_column(style="bold")
        stats_table.add_column(style="green")
        stats_table.add_row("Pages", str(result.pdf_stats["page_count"]))
        stats_table.add_row("Tables found", str(result.pdf_stats["table_count"]))
        stats_table.add_row("Characters", f"{result.pdf_stats['char_count']:,}")
        stats_table.add_row("Engine", PDF_ENGINE or "unknown")

        console.print(
            Panel(
                stats_table,
                title="[bold green]PDF Processed[/bold green]",
                subtitle=file.name,
                border_style="green",
            )
        )
        format_next_step(f"sift phase extract {session} --phase {phase}")


def _render_extracted_fields(fields: dict):
    """Render extracted field data."""
    for field_id, value in fields.items():
        if field_id.startswith("_"):
            continue
        console.print(f"[bold cyan]{field_id}:[/bold cyan]")
        if isinstance(value, list):
            for item in value:
                if isinstance(item, dict):
                    for k, v in item.items():
                        console.print(f"    [bold]{k}:[/bold] {v}")
                    console.print()
                else:
                    console.print(f"  \u2022 {item}")
        elif isinstance(value, dict):
            for k, v in value.items():
                console.print(f"  [bold]{k}:[/bold] {v}")
        else:
            console.print(f"  {value}")
        console.print()
