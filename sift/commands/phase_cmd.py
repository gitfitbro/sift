"""Phase-level commands: capture, transcribe, extract."""
import re
import typer
import yaml
import shutil
from datetime import datetime
from pathlib import Path
from rich.panel import Panel
from rich.table import Table as RichTable
from sift.ui import console, ICONS, format_next_step
from sift.models import ensure_dirs, Session
from sift import engine
from sift.pdf import extract_text_from_pdf, PDF_AVAILABLE, PDF_ENGINE

app = typer.Typer(no_args_is_help=True)


@app.command("capture")
def capture_phase(
    session: str = typer.Argument(..., help="Session name"),
    phase: str = typer.Option(..., "--phase", "-p", help="Phase ID"),
    file: Path = typer.Option(None, "--file", "-f", help="Upload audio/transcript/PDF file"),
    text: bool = typer.Option(False, "--text", "-t", help="Enter text directly"),
):
    """Capture audio, transcript, or PDF document for a session phase."""
    ensure_dirs()
    
    try:
        s = Session.load(session)
    except FileNotFoundError:
        console.print(f"[red]Session '{session}' not found[/red]")
        raise typer.Exit(1)
    
    tmpl = s.get_template()
    
    # Find phase template
    pt = next((p for p in tmpl.phases if p.id == phase), None)
    if not pt:
        console.print(f"[red]Phase '{phase}' not found in template[/red]")
        console.print(f"Available phases: {', '.join(p.id for p in tmpl.phases)}")
        raise typer.Exit(1)
    
    ps = s.phases[phase]
    phase_dir = s.phase_dir(phase)
    
    console.print(Panel(
        f"[italic]{pt.prompt}[/italic]",
        title=f"[bold]{pt.name}[/bold]",
        subtitle=f"Phase: {phase}",
    ))
    
    if file:
        # Upload mode
        if not file.exists():
            console.print(f"[red]File not found: {file}[/red]")
            raise typer.Exit(1)
        
        suffix = file.suffix.lower()
        audio_extensions = {".mp3", ".wav", ".webm", ".m4a", ".ogg", ".flac", ".mp4", ".aac"}
        text_extensions = {".txt", ".md", ".text"}
        pdf_extensions = {".pdf"}

        if suffix in audio_extensions:
            dest = phase_dir / f"audio{suffix}"
            shutil.copy2(file, dest)
            ps.audio_file = dest.name
            ps.status = "captured"
            ps.captured_at = datetime.now().isoformat()
            console.print(f"[green]Audio uploaded: {dest.name}[/green]")

        elif suffix in text_extensions:
            dest = phase_dir / "transcript.txt"
            shutil.copy2(file, dest)
            ps.transcript_file = dest.name
            ps.status = "transcribed"
            ps.captured_at = datetime.now().isoformat()
            ps.transcribed_at = datetime.now().isoformat()
            console.print(f"[green]Transcript uploaded: {dest.name}[/green]")

        elif suffix in pdf_extensions:
            # Extract text from PDF
            if not PDF_AVAILABLE:
                console.print("[red]PDF support not available. Install with: pip install pdfplumber[/red]")
                raise typer.Exit(1)

            console.print()
            with console.status("[bold cyan]Reading PDF...[/bold cyan]"):
                try:
                    pdf_text, pdf_stats = extract_text_from_pdf(file)
                except Exception as e:
                    console.print(f"[red]Failed to extract PDF text: {e}[/red]")
                    raise typer.Exit(1)

            # Check if document covers multiple phases
            from sift.document_analyzer import detect_multi_phase_content
            if len(tmpl.phases) > 1 and detect_multi_phase_content(pdf_text, tmpl.phases):
                console.print(Panel(
                    "[yellow]This document appears to contain content for multiple phases.[/yellow]\n"
                    f"Consider using: [bold cyan]sift import {session} --file {file}[/bold cyan]\n"
                    "This will analyze the document and distribute sections to the right phases automatically.",
                    title="Multi-Phase Document Detected",
                    border_style="yellow",
                ))
                from rich.prompt import Confirm as RichConfirm
                if RichConfirm.ask("  Use multi-phase import instead?", default=True):
                    from sift.commands.import_cmd import import_document
                    import_document(session, file, auto=False)
                    return

            # Save original PDF
            pdf_dest = phase_dir / "document.pdf"
            shutil.copy2(file, pdf_dest)

            # Save extracted text as transcript
            transcript_dest = phase_dir / "transcript.txt"
            transcript_dest.write_text(pdf_text)

            ps.transcript_file = transcript_dest.name
            ps.status = "transcribed"
            ps.captured_at = datetime.now().isoformat()
            ps.transcribed_at = datetime.now().isoformat()

            # Show extraction summary
            stats_table = RichTable(show_header=False, box=None, padding=(0, 2))
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

            # Show preview
            preview_text = pdf_text[:600]
            if len(pdf_text) > 600:
                preview_text += "\n..."
            console.print(Panel(
                preview_text,
                title="[dim]Content Preview[/dim]",
                border_style="dim",
            ))

        else:
            console.print(f"[red]Unsupported file type: {suffix}[/red]")
            console.print(f"Audio: {', '.join(audio_extensions)}")
            console.print(f"Text: {', '.join(text_extensions)}")
            console.print(f"PDF: {', '.join(pdf_extensions)}")
            raise typer.Exit(1)
    
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
        
        dest = phase_dir / "transcript.txt"
        dest.write_text(transcript)
        ps.transcript_file = dest.name
        ps.status = "transcribed"
        ps.captured_at = datetime.now().isoformat()
        ps.transcribed_at = datetime.now().isoformat()
        console.print(f"\n[green]Transcript saved ({len(transcript)} chars)[/green]")
    
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
            # Recurse with the file option
            capture_phase(session, phase, Path(file_path), False)
            return
        elif choice == 2:
            capture_phase(session, phase, None, True)
            return
        else:
            console.print("[dim]Skipping...[/dim]")
            return
    
    s.save()
    if ps.status == "captured":
        format_next_step(f"sift phase transcribe {session} --phase {phase}")
    else:
        format_next_step(f"sift phase extract {session} --phase {phase}")


@app.command("transcribe")
def transcribe_phase(
    session: str = typer.Argument(..., help="Session name"),
    phase: str = typer.Option(..., "--phase", "-p", help="Phase ID"),
):
    """Transcribe audio for a session phase."""
    ensure_dirs()
    
    try:
        s = Session.load(session)
    except FileNotFoundError:
        console.print(f"[red]Session '{session}' not found[/red]")
        raise typer.Exit(1)
    
    ps = s.phases.get(phase)
    if not ps:
        console.print(f"[red]Phase '{phase}' not found[/red]")
        raise typer.Exit(1)
    
    if ps.transcript_file:
        console.print(f"[yellow]Phase '{phase}' already has a transcript.[/yellow]")
        if not typer.confirm("Overwrite?"):
            raise typer.Exit(0)
    
    if not ps.audio_file:
        console.print(f"[red]No audio file for phase '{phase}'.[/red]")
        console.print(f"Capture audio first: sift phase capture {session} --phase {phase}")
        raise typer.Exit(1)
    
    audio_path = s.phase_dir(phase) / ps.audio_file
    
    with console.status("[bold]Transcribing audio...[/bold]"):
        transcript = engine.transcribe_audio(audio_path)
    
    # Save transcript
    dest = s.phase_dir(phase) / "transcript.txt"
    dest.write_text(transcript)
    
    ps.transcript_file = dest.name
    ps.status = "transcribed"
    ps.transcribed_at = datetime.now().isoformat()
    s.save()
    
    console.print(f"\n[green]Transcription complete ({len(transcript)} chars)[/green]")
    
    # Show preview
    preview = transcript[:500] + ("..." if len(transcript) > 500 else "")
    console.print(Panel(preview, title="Transcript Preview", border_style="dim"))
    
    format_next_step(f"sift phase extract {session} --phase {phase}")


@app.command("extract")
def extract_phase(
    session: str = typer.Argument(..., help="Session name"),
    phase: str = typer.Option(..., "--phase", "-p", help="Phase ID"),
):
    """Extract structured data from a phase transcript."""
    ensure_dirs()
    
    try:
        s = Session.load(session)
    except FileNotFoundError:
        console.print(f"[red]Session '{session}' not found[/red]")
        raise typer.Exit(1)
    
    tmpl = s.get_template()
    pt = next((p for p in tmpl.phases if p.id == phase), None)
    if not pt:
        console.print(f"[red]Phase '{phase}' not found[/red]")
        raise typer.Exit(1)
    
    ps = s.phases[phase]
    
    # Get transcript
    transcript = s.get_transcript(phase)
    if not transcript:
        console.print(f"[red]No transcript for phase '{phase}'.[/red]")
        console.print(f"Transcribe first: sift phase transcribe {session} --phase {phase}")
        raise typer.Exit(1)
    
    if not pt.extract:
        console.print(f"[yellow]Phase '{phase}' has no extraction fields defined.[/yellow]")
        ps.status = "complete"
        s.save()
        return
    
    # Gather context from previous phases
    context_parts = []
    for prev_pt in tmpl.phases:
        if prev_pt.id == phase:
            break
        prev_data = s.get_extracted(prev_pt.id)
        if prev_data:
            context_parts.append(f"Data from '{prev_pt.name}':\n{yaml.dump(prev_data, default_flow_style=False)}")
    
    context = "\n\n".join(context_parts) if context_parts else ""
    
    # Run extraction
    extraction_fields = [{"id": e.id, "type": e.type, "prompt": e.prompt} for e in pt.extract]
    
    with console.status(f"[bold]Extracting {len(extraction_fields)} fields...[/bold]"):
        extracted = engine.extract_structured_data(
            transcript=transcript,
            extraction_fields=extraction_fields,
            phase_name=pt.name,
            context=context,
        )
    
    # Save extracted data
    dest = s.phase_dir(phase) / "extracted.yaml"
    with open(dest, "w") as f:
        yaml.dump(extracted, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
    
    ps.extracted_file = dest.name
    ps.status = "extracted"
    ps.extracted_at = datetime.now().isoformat()
    s.save()
    
    # Display results
    console.print(f"\n[green]Extraction complete[/green]\n")
    
    for field_id, value in extracted.items():
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
    
    # Suggest next action
    remaining = [p for p in tmpl.phases if s.phases[p.id].status in ("pending", "captured", "transcribed")]
    if remaining:
        next_phase = remaining[0]
        if s.phases[next_phase.id].status == "pending":
            format_next_step(f"sift phase capture {session} --phase {next_phase.id}")
        elif s.phases[next_phase.id].status == "captured":
            format_next_step(f"sift phase transcribe {session} --phase {next_phase.id}")
        else:
            format_next_step(f"sift phase extract {session} --phase {next_phase.id}")
    else:
        console.print(f"\n  [bold green]All phases complete![/bold green]")
        format_next_step(f"sift build generate {session}")
