"""CLI commands for telemetry management."""

import typer
from sift.ui import console

app = typer.Typer(no_args_is_help=True)


@app.command()
def status():
    """Show telemetry status and what's collected."""
    from rich.panel import Panel
    from sift.telemetry.consent import ConsentManager, COLLECTED, NEVER_COLLECTED

    consent = ConsentManager()
    info = consent.status()

    enabled = info["enabled"]
    status_text = "[bold green]enabled[/bold green]" if enabled else "[bold red]disabled[/bold red]"
    source = info["source"]

    lines = [f"Status: {status_text}  (source: {source})"]

    if info["env_override"]:
        lines.append(f"Env override: SIFT_TELEMETRY={info['env_override']}")

    lines.append(f"Consent file: {info['consent_file']}")
    lines.append("")
    lines.append("[bold]What we collect:[/bold]")
    for item in COLLECTED:
        lines.append(f"  [green]+[/green] {item}")

    lines.append("")
    lines.append("[bold]What we NEVER collect:[/bold]")
    for item in NEVER_COLLECTED:
        lines.append(f"  [red]-[/red] {item}")

    console.print(Panel("\n".join(lines), title="Telemetry", border_style="cyan"))


@app.command()
def enable():
    """Opt in to anonymous telemetry."""
    from sift.telemetry.consent import ConsentManager, COLLECTED

    consent = ConsentManager()

    console.print("[bold]Telemetry helps improve sift by collecting:[/bold]")
    for item in COLLECTED:
        console.print(f"  [green]+[/green] {item}")
    console.print()

    consent.enable()
    console.print("[green]Telemetry enabled.[/green] Thank you!")
    console.print("[dim]Disable anytime: sift telemetry disable[/dim]")
    console.print("[dim]Override per-run: SIFT_TELEMETRY=disabled sift ...[/dim]")


@app.command()
def disable():
    """Opt out of telemetry."""
    from sift.telemetry.consent import ConsentManager

    consent = ConsentManager()
    consent.disable()
    console.print("[yellow]Telemetry disabled.[/yellow] No data will be collected.")
