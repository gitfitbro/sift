"""Pipeline widget - shows phase flow with status icons."""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from sift.tui.theme import ICONS, STATUS_COLORS


class PipelineWidget(Widget):
    """Horizontal pipeline showing phase status, auto-reflows on resize."""

    phases: reactive[list[dict]] = reactive(list, layout=True)
    current_phase: reactive[str] = reactive("", layout=True)

    def __init__(
        self,
        phases: list[dict] | None = None,
        current_phase: str = "",
        **kwargs,
    ):
        super().__init__(**kwargs)
        if phases:
            self.phases = phases
        self.current_phase = current_phase

    def render(self) -> Text:
        if not self.phases:
            return Text("No phases", style="dim")

        parts = []
        for phase in self.phases:
            status = phase.get("status", "pending")
            name = phase.get("name", phase.get("id", "?"))
            icon = ICONS.get(status, ICONS["pending"])
            color = STATUS_COLORS.get(status, "#808080")

            if phase.get("id") == self.current_phase:
                parts.append(Text(f"{ICONS['active']} {name}", style="bold cyan"))
            else:
                parts.append(Text(f"{icon} {name}", style=color))

        # Join with arrows, wrap if needed
        result = Text()
        for i, part in enumerate(parts):
            if i > 0:
                result.append(f" {ICONS['arrow']} ", style="dim")
            result.append_text(part)

        return result

    def update_phases(self, phases: list[dict], current_phase: str = "") -> None:
        """Update the pipeline data."""
        self.phases = phases
        self.current_phase = current_phase
