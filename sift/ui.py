"""Shared UI theme, console, and display helpers for sift."""
from rich.console import Console
from rich.theme import Theme
from rich.panel import Panel
from rich.text import Text
from rich.table import Table
from rich.align import Align

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


def banner():
    """Display the sift welcome banner."""
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
    return ICONS.get(status, ICONS["pending"])


def pipeline_view(phases: list[dict], current_phase: str = None):
    """Display a pipeline view of phases with status.

    Args:
        phases: List of dicts with 'id', 'name', 'status' keys.
        current_phase: ID of the currently active phase.
    """
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

    # Join with arrows
    pipeline = f" {ICONS['arrow']} ".join(parts)
    console.print(pipeline)
    console.print()


def step_header(step_num: int, total: int, title: str, subtitle: str = ""):
    """Display a step header with progress indicator."""
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
    console.print(Panel(
        content or "",
        title=f"[bold green]{title}[/bold green]",
        border_style="green",
    ))


def error_panel(title: str, content: str = ""):
    """Display an error panel."""
    console.print(Panel(
        content,
        title=f"[bold red]{title}[/bold red]",
        border_style="red",
    ))


def section_divider(text: str = ""):
    """Print a subtle section divider."""
    if text:
        console.print(f"\n[dim]\u2500\u2500 {text} \u2500\u2500[/dim]")
    else:
        console.print()


def format_next_step(command: str):
    """Display the next step suggestion."""
    console.print(f"\n  [bold]Next:[/bold] [cyan]{command}[/cyan]")
