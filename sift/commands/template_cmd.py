"""Template management commands."""
import typer
import yaml
from pathlib import Path
from rich.table import Table
from sift.ui import console
from sift.models import TEMPLATES_DIR, ensure_dirs, SessionTemplate

app = typer.Typer(no_args_is_help=True)


@app.command("list")
def list_templates():
    """List available session templates."""
    ensure_dirs()
    templates = list(TEMPLATES_DIR.glob("*.yaml")) + list(TEMPLATES_DIR.glob("*.yml"))
    
    if not templates:
        console.print("[yellow]No templates found.[/yellow]")
        console.print(f"Add templates to: {TEMPLATES_DIR}")
        console.print("Or run: sift template init")
        return
    
    table = Table(title="Available Templates")
    table.add_column("Name", style="bold cyan")
    table.add_column("Description")
    table.add_column("Phases", justify="center")
    table.add_column("Outputs", justify="center")
    
    for tp in sorted(templates):
        try:
            t = SessionTemplate.from_file(tp)
            table.add_row(
                tp.stem,
                t.description[:60] + ("..." if len(t.description) > 60 else ""),
                str(len(t.phases)),
                str(len(t.outputs)),
            )
        except Exception as e:
            table.add_row(tp.stem, f"[red]Error: {e}[/red]", "-", "-")
    
    console.print(table)


@app.command("show")
def show_template(name: str = typer.Argument(..., help="Template name")):
    """Show details of a template."""
    ensure_dirs()
    path = TEMPLATES_DIR / f"{name}.yaml"
    if not path.exists():
        path = TEMPLATES_DIR / f"{name}.yml"
    if not path.exists():
        console.print(f"[red]Template '{name}' not found[/red]")
        raise typer.Exit(1)
    
    t = SessionTemplate.from_file(path)
    
    console.print(f"\n[bold cyan]{t.name}[/bold cyan]")
    console.print(f"[dim]{t.description}[/dim]\n")
    
    for i, phase in enumerate(t.phases, 1):
        status = "required" if any(c.required for c in phase.capture) else "optional"
        capture_types = ", ".join(c.type for c in phase.capture) or "none"
        
        console.print(f"  [bold]{i}. {phase.name}[/bold] [dim]({phase.id})[/dim]")
        console.print(f"     Prompt: [italic]{phase.prompt[:80]}...[/italic]" if len(phase.prompt) > 80 else f"     Prompt: [italic]{phase.prompt}[/italic]")
        console.print(f"     Capture: {capture_types} ({status})")
        if phase.extract:
            fields = ", ".join(e.id for e in phase.extract)
            console.print(f"     Extract: {fields}")
        if phase.depends_on:
            console.print(f"     Depends on: {phase.depends_on}")
        console.print()
    
    if t.outputs:
        console.print("[bold]Outputs:[/bold]")
        for o in t.outputs:
            console.print(f"  - {o.type}: {o.template}")


@app.command("init")
def init_template():
    """Create a starter template interactively."""
    ensure_dirs()
    
    console.print("\n[bold]Create a new session template[/bold]\n")
    
    name = typer.prompt("Template name (e.g., workflow-extraction)")
    description = typer.prompt("Description")
    
    phases = []
    console.print("\n[bold]Define phases[/bold] (empty name to finish)\n")
    
    phase_num = 1
    while True:
        phase_name = typer.prompt(f"Phase {phase_num} name", default="")
        if not phase_name:
            break
        
        phase_id = phase_name.lower().replace(" ", "-").replace("_", "-")
        prompt = typer.prompt(f"  Prompt for '{phase_name}'")
        
        capture_type = typer.prompt(
            "  Capture type",
            default="audio",
            type=typer.Choice(["audio", "transcript", "text", "none"]),
        )
        
        # Extraction fields
        extractions = []
        console.print(f"  [dim]Define extraction fields (empty ID to finish)[/dim]")
        while True:
            field_id = typer.prompt("    Field ID", default="")
            if not field_id:
                break
            field_type = typer.prompt(
                "    Field type",
                default="list",
                type=typer.Choice(["list", "map", "text", "boolean"]),
            )
            field_prompt = typer.prompt("    Extraction prompt")
            extractions.append({
                "id": field_id,
                "type": field_type,
                "prompt": field_prompt,
            })
        
        phase = {
            "id": phase_id,
            "name": phase_name,
            "prompt": prompt,
            "capture": [{"type": capture_type, "required": True}] if capture_type != "none" else [],
            "extract": extractions,
        }
        
        if phase_num > 1:
            dep = typer.prompt("  Depends on phase", default="")
            if dep:
                phase["depends_on"] = dep
        
        phases.append(phase)
        phase_num += 1
        console.print()
    
    template = {
        "name": name,
        "description": description,
        "phases": phases,
        "outputs": [
            {"type": "yaml", "template": "session-config"},
            {"type": "markdown", "template": "session-summary"},
        ],
    }
    
    path = TEMPLATES_DIR / f"{name}.yaml"
    with open(path, "w") as f:
        yaml.dump(template, f, default_flow_style=False, sort_keys=False)
    
    console.print(f"\n[green]Template saved to {path}[/green]")


@app.command("import")
def import_template(
    path: Path = typer.Argument(..., help="Path to template YAML file"),
):
    """Import a template from a file."""
    ensure_dirs()
    if not path.exists():
        console.print(f"[red]File not found: {path}[/red]")
        raise typer.Exit(1)
    
    # Validate
    try:
        t = SessionTemplate.from_file(path)
    except Exception as e:
        console.print(f"[red]Invalid template: {e}[/red]")
        raise typer.Exit(1)
    
    dest = TEMPLATES_DIR / path.name
    import shutil
    shutil.copy2(path, dest)
    console.print(f"[green]Imported '{t.name}' to {dest}[/green]")
