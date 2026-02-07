"""Build commands: generate outputs from completed sessions."""
import typer
import yaml
from pathlib import Path
from rich.panel import Panel
from sift.ui import console
from sift.models import ensure_dirs, Session
from sift import engine

app = typer.Typer(no_args_is_help=True)


@app.command("generate")
def generate(
    session: str = typer.Argument(..., help="Session name"),
    format: str = typer.Option("all", "--format", "-f", help="Output format: yaml, markdown, all"),
):
    """Generate outputs from a session's extracted data."""
    ensure_dirs()
    
    try:
        s = Session.load(session)
    except FileNotFoundError:
        console.print(f"[red]Session '{session}' not found[/red]")
        raise typer.Exit(1)
    
    tmpl = s.get_template()
    output_dir = s.dir / "outputs"
    output_dir.mkdir(exist_ok=True)
    
    # Collect all extracted data
    all_data = {}
    all_transcripts = {}
    
    for pt in tmpl.phases:
        extracted = s.get_extracted(pt.id)
        if extracted:
            all_data[pt.id] = extracted
        
        transcript = s.get_transcript(pt.id)
        if transcript:
            all_transcripts[pt.id] = transcript
    
    if not all_data:
        console.print("[yellow]No extracted data found. Run extraction first.[/yellow]")
        raise typer.Exit(1)
    
    generated = []
    
    # ── Generate YAML config ──
    if format in ("yaml", "all"):
        config = _build_yaml_config(s, tmpl, all_data)
        config_path = output_dir / "session-config.yaml"
        with open(config_path, "w") as f:
            yaml.dump(config, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        generated.append(("YAML Config", config_path))
    
    # ── Generate Markdown summary ──
    if format in ("markdown", "all"):
        md = _build_markdown(s, tmpl, all_data, all_transcripts)
        md_path = output_dir / "session-summary.md"
        md_path.write_text(md)
        generated.append(("Markdown Summary", md_path))
    
    # ── Generate consolidated extraction ──
    if format in ("yaml", "all"):
        consolidated = _build_consolidated(s, tmpl, all_data)
        con_path = output_dir / "extracted-data.yaml"
        with open(con_path, "w") as f:
            yaml.dump(consolidated, f, default_flow_style=False, sort_keys=False, allow_unicode=True)
        generated.append(("Consolidated Data", con_path))
    
    # Show results
    console.print(f"\n[green bold]Outputs generated:[/green bold]\n")
    for label, path in generated:
        console.print(f"  [bold]{label}[/bold]: {path}")
    
    console.print(f"\n[dim]All outputs in: {output_dir}[/dim]")


def _build_yaml_config(s: Session, tmpl, all_data: dict) -> dict:
    """Build the session configuration YAML."""
    config = {
        "session": {
            "name": s.name,
            "template": s.template_name,
            "created": s.created_at,
            "status": s.status,
        },
        "phases_completed": [],
        "data": {},
    }
    
    for pt in tmpl.phases:
        ps = s.phases.get(pt.id)
        if ps and ps.status in ("extracted", "complete"):
            config["phases_completed"].append({
                "id": pt.id,
                "name": pt.name,
                "captured_at": ps.captured_at,
                "extracted_at": ps.extracted_at,
            })
        
        if pt.id in all_data:
            config["data"][pt.id] = all_data[pt.id]
    
    return config


def _build_markdown(s: Session, tmpl, all_data: dict, all_transcripts: dict) -> str:
    """Build a markdown summary document."""
    lines = [
        f"# {tmpl.name}: Session Summary",
        f"",
        f"**Session:** {s.name}  ",
        f"**Template:** {s.template_name}  ",
        f"**Created:** {s.created_at[:16]}  ",
        f"**Status:** {s.status}",
        f"",
        "---",
        "",
    ]
    
    for pt in tmpl.phases:
        ps = s.phases.get(pt.id)
        if not ps or ps.status == "pending":
            continue
        
        lines.append(f"## {pt.name}")
        lines.append("")
        
        # Show extracted data
        extracted = all_data.get(pt.id, {})
        if extracted:
            for field_id, value in extracted.items():
                if field_id.startswith("_"):
                    continue
                
                lines.append(f"### {field_id.replace('_', ' ').title()}")
                lines.append("")
                
                if isinstance(value, list):
                    for item in value:
                        if isinstance(item, dict):
                            for k, v in item.items():
                                lines.append(f"- **{k}**: {v}")
                        else:
                            lines.append(f"- {item}")
                elif isinstance(value, dict):
                    for k, v in value.items():
                        lines.append(f"- **{k}**: {v}")
                else:
                    lines.append(str(value))
                
                lines.append("")
        
        lines.append("---")
        lines.append("")
    
    # Append raw transcripts at the end
    if all_transcripts:
        lines.append("## Raw Transcripts")
        lines.append("")
        for phase_id, transcript in all_transcripts.items():
            pt = next((p for p in tmpl.phases if p.id == phase_id), None)
            name = pt.name if pt else phase_id
            lines.append(f"### {name}")
            lines.append("")
            lines.append("```")
            lines.append(transcript[:3000])
            if len(transcript) > 3000:
                lines.append(f"\n... [truncated, {len(transcript)} total chars]")
            lines.append("```")
            lines.append("")
    
    return "\n".join(lines)


def _build_consolidated(s: Session, tmpl, all_data: dict) -> dict:
    """Build a flat consolidated view of all extracted data."""
    consolidated = {
        "meta": {
            "session": s.name,
            "template": s.template_name,
            "generated_at": s.updated_at,
        }
    }
    
    # Flatten all extractions into one namespace
    for phase_id, data in all_data.items():
        if isinstance(data, dict):
            for k, v in data.items():
                if not k.startswith("_"):
                    consolidated[k] = v
    
    return consolidated


@app.command("summary")
def ai_summary(
    session: str = typer.Argument(..., help="Session name"),
):
    """Generate an AI-powered narrative summary of the session."""
    ensure_dirs()
    
    try:
        s = Session.load(session)
    except FileNotFoundError:
        console.print(f"[red]Session '{session}' not found[/red]")
        raise typer.Exit(1)
    
    tmpl = s.get_template()
    
    # Collect all data
    session_data = {}
    for pt in tmpl.phases:
        phase_bundle = {}
        transcript = s.get_transcript(pt.id)
        if transcript:
            phase_bundle["transcript_preview"] = transcript[:2000]
        extracted = s.get_extracted(pt.id)
        if extracted:
            phase_bundle["extracted"] = extracted
        if phase_bundle:
            session_data[pt.name] = phase_bundle
    
    if not session_data:
        console.print("[yellow]No data to summarize.[/yellow]")
        raise typer.Exit(1)
    
    with console.status("[bold]Generating AI summary...[/bold]"):
        summary = engine.generate_summary(session_data, tmpl.name)
    
    # Save
    output_dir = s.dir / "outputs"
    output_dir.mkdir(exist_ok=True)
    summary_path = output_dir / "ai-summary.md"
    summary_path.write_text(summary)
    
    console.print(Panel(summary, title="AI Summary", border_style="green"))
    console.print(f"\n[dim]Saved to: {summary_path}[/dim]")
