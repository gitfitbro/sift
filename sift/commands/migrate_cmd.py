"""CLI command for schema migrations."""

from __future__ import annotations

import typer
from rich.table import Table

from sift.completions import complete_session_name
from sift.error_handler import handle_errors
from sift.ui import ICONS, console

app = typer.Typer(no_args_is_help=False)


@app.callback(invoke_without_command=True)
@handle_errors
def migrate(
    dry_run: bool = typer.Option(False, "--dry-run", help="Preview changes without applying"),
    session: str = typer.Option(
        None,
        "--session",
        "-s",
        help="Migrate a specific session only",
        autocompletion=complete_session_name,
    ),
    template: str = typer.Option(
        None,
        "--template",
        "-t",
        help="Migrate a specific template only",
    ),
) -> None:
    """Migrate sessions and templates to the current schema version."""
    from sift.core.migration_service import MigrationService

    svc = MigrationService()

    if dry_run:
        console.print("[dim]Dry run mode - no changes will be written[/dim]\n")

    if session:
        result = svc.migrate_session(session, dry_run=dry_run)
        _display_single_result(result)
        return

    if template:
        result = svc.migrate_template(template, dry_run=dry_run)
        _display_single_result(result)
        return

    # Migrate everything
    summary = svc.migrate_all(dry_run=dry_run)

    if not summary.sessions and not summary.templates:
        console.print("[dim]No sessions or templates found to migrate.[/dim]")
        return

    table = Table(title="Migration Results", show_header=True, border_style="cyan")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("Version", justify="center")
    table.add_column("Status", justify="center")
    table.add_column("Details")

    for result in summary.sessions:
        icon = ICONS["complete"] if result.migrated else ICONS["pending"]
        version_str = f"v{result.source_version} -> v{result.target_version}"
        table.add_row(
            result.name,
            "session",
            version_str,
            icon,
            "; ".join(result.changes),
        )

    for result in summary.templates:
        icon = ICONS["complete"] if result.migrated else ICONS["pending"]
        version_str = f"v{result.source_version} -> v{result.target_version}"
        table.add_row(
            result.name,
            "template",
            version_str,
            icon,
            "; ".join(result.changes),
        )

    console.print(table)

    console.print(
        f"\n[bold]{summary.total_migrated}[/bold] migrated, "
        f"[dim]{summary.total_skipped} already current[/dim]"
    )
    if dry_run and summary.total_migrated > 0:
        console.print("[yellow]Re-run without --dry-run to apply changes.[/yellow]")


def _display_single_result(result: object) -> None:
    """Display a single migration result."""
    from sift.core.migration_service import MigrationResult

    if not isinstance(result, MigrationResult):
        return

    if result.migrated:
        icon = ICONS["complete"]
        console.print(
            f"{icon} [bold]{result.name}[/bold]: "
            f"v{result.source_version} -> v{result.target_version}"
        )
        for change in result.changes:
            console.print(f"  {change}")
        if result.dry_run:
            console.print("[yellow]  (dry run - no changes written)[/yellow]")
    else:
        icon = ICONS["pending"]
        console.print(f"{icon} [bold]{result.name}[/bold]: already at v{result.target_version}")
