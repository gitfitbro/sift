"""Phase-level commands: capture, transcribe, extract - thin CLI wrappers."""
import typer
from pathlib import Path
from rich.panel import Panel
from rich.table import Table as RichTable
from sift.ui import console, ICONS, format_next_step
from sift.core.extraction_service import ExtractionService
from sift.pdf import PDF_ENGINE
from sift.completions import complete_session_name, complete_phase_id

app = typer.Typer(no_args_is_help=True)

_svc = ExtractionService()


@app.command("capture")
def capture_phase(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
    phase: str = typer.Option(..., "--phase", "-p", help="Phase ID", autocompletion=complete_phase_id),
    file: Path = typer.Option(None, "--file", "-f", help="Upload audio/transcript/PDF file"),
    text: bool = typer.Option(False, "--text", "-t", help="Enter text directly"),
):
    """Capture audio, transcript, or PDF document for a session phase."""
    if file:
        try:
            result = _svc.capture_file(session, phase, file)
        except FileNotFoundError as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)
        except (ValueError, ImportError) as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)

        _render_capture_result(result, file, session, phase)

        # If multi-phase detected, suggest import command
        if result.multi_phase_detected:
            console.print(Panel(
                "[yellow]This document appears to contain content for multiple phases.[/yellow]\n"
                f"Consider using: [bold cyan]sift import {session} --file {file}[/bold cyan]\n"
                "This will analyze the document and distribute sections to the right phases automatically.",
                title="Multi-Phase Document Detected",
                border_style="yellow",
            ))

    elif text:
        # Direct text entry mode
        console.print("\n[bold]Enter transcript text.[/bold]")
        console.print("[dim]Type or paste your text. Enter an empty line followed by 'END' to finish.[/dim]\n")

        lines = []
        while True:
            try:
                line = input()
                if line.strip() == "END":
                    break
                lines.append(line)
            except EOFError:
                break

        transcript = "\n".join(lines)
        if not transcript.strip():
            console.print("[yellow]No text entered. Aborting.[/yellow]")
            raise typer.Exit(0)

        try:
            result = _svc.capture_text(session, phase, transcript)
        except (FileNotFoundError, ValueError) as e:
            console.print(f"[red]{e}[/red]")
            raise typer.Exit(1)

        console.print(f"\n[green]Transcript saved ({result.char_count} chars)[/green]")
        format_next_step(f"sift phase extract {session} --phase {phase}")

    else:
        # Interactive mode — ask what to do
        console.print("\nHow would you like to capture this phase?\n")
        console.print("  [bold]1[/bold]. Upload a file (audio, transcript, or PDF)")
        console.print("  [bold]2[/bold]. Enter/paste text directly")
        console.print("  [bold]3[/bold]. Skip for now")
        console.print()

        choice = typer.prompt("Choice", type=int, default=1)

        if choice == 1:
            file_path = typer.prompt("File path")
            capture_phase(session, phase, Path(file_path), False)
            return
        elif choice == 2:
            capture_phase(session, phase, None, True)
            return
        else:
            console.print("[dim]Skipping...[/dim]")
            return


@app.command("transcribe")
def transcribe_phase(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
    phase: str = typer.Option(..., "--phase", "-p", help="Phase ID", autocompletion=complete_phase_id),
):
    """Transcribe audio for a session phase."""
    try:
        result = _svc.transcribe_phase(session, phase)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Transcription error: {e}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[green]Transcription complete ({result.char_count} chars)[/green]")
    console.print(Panel(
        result.transcript_preview,
        title="Transcript Preview",
        border_style="dim",
    ))
    format_next_step(f"sift phase extract {session} --phase {phase}")


@app.command("extract")
def extract_phase(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
    phase: str = typer.Option(..., "--phase", "-p", help="Phase ID", autocompletion=complete_phase_id),
):
    """Extract structured data from a phase transcript."""
    try:
        with console.status(f"[bold]Extracting structured data...[/bold]"):
            result = _svc.extract_phase(session, phase)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except Exception as e:
        console.print(f"[red]Extraction error: {e}[/red]")
        raise typer.Exit(1)

    if not result.fields:
        console.print(f"[yellow]Phase '{phase}' has no extraction fields defined. Marked complete.[/yellow]")
        return

    console.print(f"\n[green]Extraction complete[/green]\n")
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
        console.print(f"\n  [bold green]All phases complete![/bold green]")
        format_next_step(f"sift build generate {session}")


# ── Render helpers ──

def _render_capture_result(result, file: Path, session: str, phase: str):
    """Render capture result based on file type."""
    if result.file_type == "audio":
        console.print(f"[green]Audio uploaded[/green]")
        format_next_step(f"sift phase transcribe {session} --phase {phase}")

    elif result.file_type == "text":
        console.print(f"[green]Transcript uploaded[/green]")
        format_next_step(f"sift phase extract {session} --phase {phase}")

    elif result.file_type == "pdf" and result.pdf_stats:
        stats_table = RichTable(show_header=False, box=None, padding=(0, 2))
        stats_table.add_column(style="bold")
        stats_table.add_column(style="green")
        stats_table.add_row("Pages", str(result.pdf_stats["page_count"]))
        stats_table.add_row("Tables found", str(result.pdf_stats["table_count"]))
        stats_table.add_row("Characters", f"{result.pdf_stats['char_count']:,}")
        stats_table.add_row("Engine", PDF_ENGINE or "unknown")

        console.print(Panel(
            stats_table,
            title="[bold green]PDF Processed[/bold green]",
            subtitle=file.name,
            border_style="green",
        ))
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
