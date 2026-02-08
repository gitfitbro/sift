"""Template management commands - thin CLI wrappers over TemplateService."""
import typer
import yaml
from pathlib import Path
from rich.table import Table
from sift.ui import console
from sift.core.template_service import TemplateService

app = typer.Typer(no_args_is_help=True)

_svc = TemplateService()


@app.command("list")
def list_templates():
    """List available session templates."""
    templates = _svc.list_templates()

    if not templates:
        console.print("[yellow]No templates found.[/yellow]")
        console.print(f"Add templates to the templates directory.")
        console.print("Or run: sift template init")
        return

    table = Table(title="Available Templates")
    table.add_column("Name", style="bold cyan")
    table.add_column("Description")
    table.add_column("Phases", justify="center")
    table.add_column("Outputs", justify="center")

    for t in templates:
        table.add_row(
            t.stem,
            t.description[:60] + ("..." if len(t.description) > 60 else ""),
            str(t.phase_count),
            str(t.output_count),
        )

    console.print(table)


@app.command("show")
def show_template(name: str = typer.Argument(..., help="Template name")):
    """Show details of a template."""
    try:
        detail = _svc.show_template(name)
    except FileNotFoundError:
        console.print(f"[red]Template '{name}' not found[/red]")
        raise typer.Exit(1)

    console.print(f"\n[bold cyan]{detail.name}[/bold cyan]")
    console.print(f"[dim]{detail.description}[/dim]\n")

    for i, phase in enumerate(detail.phases, 1):
        capture_types = ", ".join(phase.capture_types) or "none"
        status = "required" if phase.required else "optional"

        console.print(f"  [bold]{i}. {phase.name}[/bold] [dim]({phase.id})[/dim]")
        prompt_display = phase.prompt[:80] + "..." if len(phase.prompt) > 80 else phase.prompt
        console.print(f"     Prompt: [italic]{prompt_display}[/italic]")
        console.print(f"     Capture: {capture_types} ({status})")
        if phase.extract_field_ids:
            fields = ", ".join(phase.extract_field_ids)
            console.print(f"     Extract: {fields}")
        if phase.depends_on:
            console.print(f"     Depends on: {phase.depends_on}")
        console.print()

    if detail.outputs:
        console.print("[bold]Outputs:[/bold]")
        for o in detail.outputs:
            console.print(f"  - {o['type']}: {o['template']}")


@app.command("init")
def init_template():
    """Create a starter template interactively."""
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

    template_data = {
        "name": name,
        "description": description,
        "phases": phases,
        "outputs": [
            {"type": "yaml", "template": "session-config"},
            {"type": "markdown", "template": "session-summary"},
        ],
    }

    try:
        path = _svc.create_template(template_data)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    console.print(f"\n[green]Template saved to {path}[/green]")


@app.command("import")
def import_template(
    path: Path = typer.Argument(..., help="Path to template YAML file"),
):
    """Import a template from a file."""
    try:
        info = _svc.import_template(path)
    except FileNotFoundError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)
    except ValueError as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Imported '{info.name}' ({info.phase_count} phases)[/green]")
