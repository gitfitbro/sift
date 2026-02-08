"""Document import command: analyze and distribute multi-phase documents."""
import typer
import shutil
from datetime import datetime
from pathlib import Path
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt, Confirm
from sift.ui import console, ICONS, format_next_step
from sift.models import ensure_dirs, Session
from sift.pdf import extract_text_from_pdf, PDF_AVAILABLE, PDF_ENGINE
from sift.document_analyzer import analyze_document_for_phases
from sift.error_handler import handle_errors

app = typer.Typer(no_args_is_help=True)


@app.command("document")
@handle_errors
def import_document(
    session: str = typer.Argument(..., help="Session name"),
    file: Path = typer.Option(..., "--file", "-f", help="PDF or text file to import"),
    auto: bool = typer.Option(False, "--auto", help="Skip confirmation, auto-apply mapping"),
):
    """Analyze a document and distribute sections to matching session phases."""
    ensure_dirs()

    s = Session.load(session)  # raises SessionNotFoundError

    if not file.exists():
        from sift.errors import CaptureError
        raise CaptureError(f"File not found: {file}", file_path=str(file))

    tmpl = s.get_template()

    # ── Extract text ──
    suffix = file.suffix.lower()
    if suffix == ".pdf":
        if not PDF_AVAILABLE:
            from sift.errors import CaptureError
            raise CaptureError("PDF support not available. Install with: pip install pdfplumber")

        with console.status("[bold cyan]Reading PDF...[/bold cyan]"):
            try:
                doc_text, pdf_stats = extract_text_from_pdf(file)
            except Exception as e:
                console.print(f"[red]Failed to extract PDF text: {e}[/red]")
                raise typer.Exit(1)

        # Show extraction stats
        stats_table = Table(show_header=False, box=None, padding=(0, 2))
        stats_table.add_column(style="bold")
        stats_table.add_column(style="green")
        stats_table.add_row("Pages", str(pdf_stats["page_count"]))
        stats_table.add_row("Tables found", str(pdf_stats["table_count"]))
        stats_table.add_row("Characters", f"{pdf_stats['char_count']:,}")
        stats_table.add_row("Engine", PDF_ENGINE)
        console.print(Panel(
            stats_table,
            title="[bold green]PDF Processed[/bold green]",
            subtitle=file.name,
            border_style="green",
        ))

    elif suffix in (".txt", ".md", ".text"):
        doc_text = file.read_text()
        if not doc_text.strip():
            console.print("[red]File is empty.[/red]")
            raise typer.Exit(1)
        console.print(f"[green]Text file loaded ({len(doc_text):,} chars)[/green]")

    else:
        from sift.errors import CaptureError
        raise CaptureError(f"Unsupported file type: {suffix}. Use PDF or text files.", file_path=str(file))

    # ── Store document at session level ──
    docs_dir = s.dir / "documents"
    docs_dir.mkdir(exist_ok=True)
    doc_id = f"doc-{datetime.now().strftime('%H%M%S')}"
    doc_dest = docs_dir / f"{doc_id}{suffix}"
    shutil.copy2(file, doc_dest)

    # ── Analyze document against template phases ──
    console.print()
    with console.status("[bold cyan]Analyzing document against template phases...[/bold cyan]"):
        mappings = analyze_document_for_phases(doc_text, tmpl.phases, tmpl.name)

    if not mappings:
        console.print("[yellow]Could not determine phase mappings for this document.[/yellow]")
        console.print("[dim]You can still capture it manually per-phase.[/dim]")
        raise typer.Exit(0)

    # ── Display mapping results ──
    mapped_ids = {m.phase_id for m in mappings}
    unmapped_phases = [p for p in tmpl.phases if p.id not in mapped_ids]

    result_table = Table(
        title="Document Analysis",
        show_header=True,
        border_style="cyan",
        title_style="bold cyan",
    )
    result_table.add_column("#", justify="center", width=3)
    result_table.add_column("Phase", min_width=22)
    result_table.add_column("Pages", min_width=8)
    result_table.add_column("Section", min_width=20)
    result_table.add_column("Match", min_width=8)

    for i, pt in enumerate(tmpl.phases, 1):
        mapping = next((m for m in mappings if m.phase_id == pt.id), None)
        if mapping:
            confidence_style = {
                "high": "green",
                "medium": "yellow",
                "low": "red",
            }.get(mapping.confidence, "dim")
            result_table.add_row(
                str(i),
                pt.name,
                mapping.matched_pages,
                mapping.section_title,
                f"[{confidence_style}]{mapping.confidence}[/{confidence_style}]",
            )
        else:
            result_table.add_row(
                str(i),
                f"[dim]{pt.name}[/dim]",
                "[dim]--[/dim]",
                "[dim](no match)[/dim]",
                "[dim]--[/dim]",
            )

    console.print(result_table)

    # Warn about unmapped phases
    if unmapped_phases:
        names = ", ".join(p.name for p in unmapped_phases)
        console.print(f"\n  [yellow]{ICONS['bullet']} {names}[/yellow] [dim]had no matching content.[/dim]")
        console.print(f"  [dim]These phases may need separate audio recordings or text input.[/dim]")

    # Check for phases that already have data
    overwrite_phases = []
    for m in mappings:
        ps = s.phases.get(m.phase_id)
        if ps and ps.status not in ("pending",):
            overwrite_phases.append(m.phase_name)

    if overwrite_phases:
        console.print(f"\n  [yellow]Warning: {', '.join(overwrite_phases)} already have data.[/yellow]")

    # ── Confirm and distribute ──
    if not auto:
        console.print()
        if not Confirm.ask(f"  Distribute content to {len(mappings)} matched phases?", default=True):
            console.print("  [dim]Import cancelled.[/dim]")
            raise typer.Exit(0)

    # Distribute content to phases
    console.print()
    for mapping in mappings:
        ps = s.phases[mapping.phase_id]
        phase_dir = s.phase_dir(mapping.phase_id)

        # Write transcript
        transcript_dest = phase_dir / "transcript.txt"
        transcript_dest.write_text(mapping.content)

        # Copy source PDF to phase dir too
        if suffix == ".pdf":
            pdf_dest = phase_dir / "document.pdf"
            shutil.copy2(file, pdf_dest)

        # Update phase state
        now = datetime.now().isoformat()
        ps.transcript_file = "transcript.txt"
        ps.status = "transcribed"
        ps.captured_at = now
        ps.transcribed_at = now
        ps.source_document = doc_id
        ps.source_pages = mapping.matched_pages

        char_count = len(mapping.content)
        console.print(
            f"  {ICONS['complete']} {mapping.phase_name:30s} "
            f"[green]{char_count:,} chars[/green] [dim](pages {mapping.matched_pages})[/dim]"
        )

    # Record document in session
    s.documents.append({
        "id": doc_id,
        "filename": file.name,
        "imported_at": datetime.now().isoformat(),
        "phases_mapped": [m.phase_id for m in mappings],
    })

    s.save()

    # Suggest next step
    first_transcribed = next(
        (p for p in tmpl.phases if s.phases[p.id].status == "transcribed"),
        None,
    )
    if first_transcribed:
        console.print()
        format_next_step(f"sift phase extract {session} --phase {first_transcribed.id}")
