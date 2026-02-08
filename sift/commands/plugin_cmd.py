"""Plugin listing command."""
from __future__ import annotations

import typer
from rich.table import Table

from sift.ui import console, ICONS

app = typer.Typer(no_args_is_help=False)


GROUP_LABELS = {
    "sift.providers": "Provider",
    "sift.analyzers": "Analyzer",
    "sift.output_formatters": "Formatter",
}


@app.callback(invoke_without_command=True)
def plugins(
    providers: bool = typer.Option(False, "--providers", help="Show provider plugins only"),
    analyzers: bool = typer.Option(False, "--analyzers", help="Show analyzer plugins only"),
    formatters: bool = typer.Option(False, "--formatters", help="Show formatter plugins only"),
):
    """List all discovered plugins."""
    from sift.plugins import list_all_plugins, PROVIDER_GROUP, ANALYZER_GROUP, FORMATTER_GROUP

    all_plugins = list_all_plugins()

    # Filter if requested
    if providers:
        all_plugins = [p for p in all_plugins if p.group == PROVIDER_GROUP]
    elif analyzers:
        all_plugins = [p for p in all_plugins if p.group == ANALYZER_GROUP]
    elif formatters:
        all_plugins = [p for p in all_plugins if p.group == FORMATTER_GROUP]

    if not all_plugins:
        console.print("[dim]No plugins found.[/dim]")
        return

    table = Table(title="Sift Plugins", show_header=True, border_style="cyan")
    table.add_column("Name", style="cyan")
    table.add_column("Type")
    table.add_column("Module", style="dim")
    table.add_column("Status", justify="center")

    for plugin in sorted(all_plugins, key=lambda p: (p.group, p.name)):
        type_label = GROUP_LABELS.get(plugin.group, plugin.group)
        if plugin.loaded:
            status = ICONS.get("complete", "[green]OK[/green]")
        else:
            status = f"[red]{plugin.error[:40]}[/red]" if plugin.error else ICONS.get("error", "[red]ERR[/red]")
        table.add_row(plugin.name, type_label, plugin.module, status)

    console.print(table)
    console.print(f"\n[dim]{len(all_plugins)} plugin(s) discovered[/dim]")
