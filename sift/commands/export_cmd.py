"""Export and import commands for sessions and templates."""
from __future__ import annotations

from pathlib import Path

import typer

from sift.ui import console
from sift.completions import complete_session_name, complete_template_name

app = typer.Typer(no_args_is_help=True)


@app.command("session")
def export_session(
    session: str = typer.Argument(..., help="Session name", autocompletion=complete_session_name),
    format: str = typer.Option("zip", "--format", "-f", help="Export format: zip, json, yaml"),
    output: str = typer.Option(None, "--output", "-o", help="Output directory (default: current dir)"),
    include_audio: bool = typer.Option(False, "--include-audio", help="Include audio files in ZIP export"),
):
    """Export a session as a portable archive."""
    from sift.core.export_service import ExportService
    from sift.errors import SiftError

    output_dir = Path(output) if output else None

    try:
        svc = ExportService()
        result = svc.export_session(session, format=format, output_dir=output_dir, include_audio=include_audio)
    except (SiftError, ValueError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    size_str = _format_size(result.size_bytes)
    console.print(f"[green]Exported[/green] {result.session_name} ({result.format})")
    console.print(f"  [dim]File:[/dim]  {result.output_path}")
    console.print(f"  [dim]Size:[/dim]  {size_str} ({result.file_count} files)")


@app.command("template")
def export_template(
    template: str = typer.Argument(..., help="Template name", autocompletion=complete_template_name),
    output: str = typer.Option(None, "--output", "-o", help="Output file path"),
):
    """Export a template as a YAML file."""
    from sift.core.export_service import ExportService
    from sift.errors import SiftError

    output_path = Path(output) if output else None

    try:
        svc = ExportService()
        result_path = svc.export_template(template, output_path=output_path)
    except (SiftError, FileNotFoundError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Exported template[/green] to {result_path}")


# Separate Typer app for import commands (wired as top-level 'import-data')
import_app = typer.Typer(no_args_is_help=True)


@import_app.command("session")
def import_session(
    file: str = typer.Argument(..., help="Path to .sift.zip, .json, or .yaml file"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing session"),
):
    """Import a session from an exported file."""
    from sift.core.export_service import ExportService
    from sift.errors import SiftError

    source_path = Path(file)
    try:
        svc = ExportService()
        result = svc.import_session(source_path, overwrite=overwrite)
    except (SiftError, FileNotFoundError, ValueError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Imported session[/green] '{result.session_name}' ({result.phase_count} phases)")
    if result.overwritten:
        console.print("  [yellow]Previous session was overwritten[/yellow]")


@import_app.command("template")
def import_template(
    file: str = typer.Argument(..., help="Path to template YAML file"),
    overwrite: bool = typer.Option(False, "--overwrite", help="Overwrite existing template"),
):
    """Import a template from a YAML file."""
    from sift.core.export_service import ExportService
    from sift.errors import SiftError

    source_path = Path(file)
    try:
        svc = ExportService()
        result_path = svc.import_template(source_path, overwrite=overwrite)
    except (SiftError, FileNotFoundError, ValueError) as e:
        console.print(f"[red]{e}[/red]")
        raise typer.Exit(1)

    console.print(f"[green]Imported template[/green] to {result_path}")


def _format_size(size_bytes: int) -> str:
    """Format bytes as human-readable size."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
