"""Shared UI theme, console, and display helpers for sift."""

import json
import sys
from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.align import Align

# ── Output Mode State ──
_plain_mode: bool = False
_json_mode: bool = False


def set_plain_mode(enabled: bool = True) -> None:
    """Enable or disable plain text output (no colors, no panels, ASCII only)."""
    global _plain_mode, console
    _plain_mode = enabled
    if enabled:
        console = Console(no_color=True, highlight=False)


def set_json_mode(enabled: bool = True) -> None:
    """Enable or disable JSON output mode."""
    global _json_mode
    _json_mode = enabled


def is_plain() -> bool:
    """Check if plain output mode is active."""
    return _plain_mode


def is_json() -> bool:
    """Check if JSON output mode is active."""
    return _json_mode


def print_json_output(data: dict | list) -> None:
    """Print data as formatted JSON to stdout."""
    print(json.dumps(data, indent=2, default=str))


# ── Theme ──
SIFT_THEME = Theme({
    "info": "cyan",
    "success": "bold green",
    "warning": "yellow",
    "error": "bold red",
    "phase.name": "bold blue",
    "phase.active": "bold cyan",
    "phase.complete": "green",
    "phase.pending": "dim",
    "brand": "bold cyan",
    "muted": "dim",
})

console = Console(theme=SIFT_THEME)

# ── Status Icons ──
ICONS = {
    "complete": "[green]\u2714[/green]",       # checkmark
    "active": "[cyan]\u25b6[/cyan]",           # play triangle
    "pending": "[dim]\u25cb[/dim]",            # empty circle
    "captured": "[yellow]\u25c9[/yellow]",     # dotted circle
    "transcribed": "[blue]\u25c9[/blue]",      # dotted circle
    "extracted": "[green]\u25c9[/green]",      # dotted circle
    "error": "[red]\u2718[/red]",              # cross
    "arrow": "[dim]\u2500\u2500\u25b8[/dim]",  # arrow ──▸
    "bullet": "[cyan]\u2022[/cyan]",           # bullet
}

# ASCII equivalents for plain mode
PLAIN_ICONS = {
    "complete": "[OK]",
    "active": "[>>]",
    "pending": "[ ]",
    "captured": "[**]",
    "transcribed": "[**]",
    "extracted": "[**]",
    "error": "[!!]",
    "arrow": "-->",
    "bullet": "*",
}


def banner():
    """Display the sift welcome banner."""
    if _json_mode:
        return
    if _plain_mode:
        print("sift - Structured Session Capture & AI Extraction CLI")
        print()
        return

    title = Text()
    title.append("s i f t", style="bold cyan")

    subtitle = Text()
    subtitle.append("Structured Session Capture & AI Extraction", style="dim italic")

    content = Text.from_markup(
        "\n"
        "[bold cyan]  s i f t[/bold cyan]\n"
        "[dim]  Structured Session Capture[/dim]\n"
        "[dim]  & AI Extraction CLI[/dim]\n"
    )

    console.print(Panel(
        Align.center(content),
        border_style="cyan",
        padding=(0, 4),
    ))


def phase_status_icon(status: str) -> str:
    """Get the appropriate icon for a phase status."""
    if _plain_mode:
        return PLAIN_ICONS.get(status, PLAIN_ICONS["pending"])
    return ICONS.get(status, ICONS["pending"])


def pipeline_view(phases: list[dict], current_phase: str = None):
    """Display a pipeline view of phases with status."""
    if _json_mode:
        print_json_output([{
            "id": p["id"],
            "name": p["name"],
            "status": p["status"],
            "current": p["id"] == current_phase,
        } for p in phases])
        return

    if _plain_mode:
        for phase in phases:
            status = phase["status"]
            name = phase["name"]
            icon = PLAIN_ICONS.get(status, PLAIN_ICONS["pending"])
            marker = " <-- current" if phase["id"] == current_phase else ""
            print(f"  {icon} {name}{marker}")
        print()
        return

    parts = []
    for i, phase in enumerate(phases):
        status = phase["status"]
        name = phase["name"]

        if phase["id"] == current_phase:
            part = f"[bold cyan]\u25b6 {name}[/bold cyan]"
        elif status in ("extracted", "complete"):
            part = f"[green]\u2714 {name}[/green]"
        elif status in ("captured", "transcribed"):
            part = f"[yellow]\u25c9 {name}[/yellow]"
        else:
            part = f"[dim]\u25cb {name}[/dim]"

        parts.append(part)

    pipeline = f" {ICONS['arrow']} ".join(parts)
    console.print(pipeline)
    console.print()


def step_header(step_num: int, total: int, title: str, subtitle: str = ""):
    """Display a step header with progress indicator."""
    if _json_mode:
        return
    if _plain_mode:
        sub = f" - {subtitle}" if subtitle else ""
        print(f"--- Step {step_num}/{total}: {title}{sub} ---")
        return

    progress = f"[dim]Step {step_num} of {total}[/dim]"

    content = f"[bold]{title}[/bold]"
    if subtitle:
        content += f"\n[dim italic]{subtitle}[/dim italic]"

    console.print(Panel(
        content,
        title=progress,
        border_style="blue",
        padding=(0, 2),
    ))


def success_panel(title: str, content=None):
    """Display a success panel."""
    if _json_mode:
        return
    if _plain_mode:
        print(f"OK: {title}")
        if content:
            print(f"  {content}")
        return

    console.print(Panel(
        content or "",
        title=f"[bold green]{title}[/bold green]",
        border_style="green",
    ))


def error_panel(title: str, content: str = ""):
    """Display an error panel."""
    if _json_mode:
        print_json_output({"error": title, "detail": content})
        return
    if _plain_mode:
        print(f"ERROR: {title}", file=sys.stderr)
        if content:
            print(f"  {content}", file=sys.stderr)
        return

    console.print(Panel(
        content,
        title=f"[bold red]{title}[/bold red]",
        border_style="red",
    ))


def section_divider(text: str = ""):
    """Print a subtle section divider."""
    if _json_mode:
        return
    if _plain_mode:
        if text:
            print(f"\n-- {text} --")
        else:
            print()
        return

    if text:
        console.print(f"\n[dim]\u2500\u2500 {text} \u2500\u2500[/dim]")
    else:
        console.print()


def format_next_step(command: str):
    """Display the next step suggestion."""
    if _json_mode:
        return
    if _plain_mode:
        print(f"\n  Next: {command}")
        return

    console.print(f"\n  [bold]Next:[/bold] [cyan]{command}[/cyan]")
