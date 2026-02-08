"""Phase panel widget - displays phase details with prompt and fields."""

from __future__ import annotations

from rich.text import Text
from textual.reactive import reactive
from textual.widget import Widget

from sift.tui.theme import ICONS, STATUS_COLORS


class PhasePanel(Widget):
    """Displays details for a single phase."""

    phase_name: reactive[str] = reactive("")
    phase_prompt: reactive[str] = reactive("")
    phase_status: reactive[str] = reactive("pending")
    step_num: reactive[int] = reactive(0)
    total_steps: reactive[int] = reactive(0)
    extract_fields: reactive[list[str]] = reactive(list)

    def render(self) -> Text:
        icon = ICONS.get(self.phase_status, ICONS["pending"])
        color = STATUS_COLORS.get(self.phase_status, "#808080")

        result = Text()

        # Step header
        if self.step_num and self.total_steps:
            result.append(f"Step {self.step_num} of {self.total_steps}", style="dim")
            result.append("\n")

        # Phase name with status
        result.append(f"{icon} ", style=color)
        result.append(self.phase_name, style="bold")
        result.append(f"  [{self.phase_status}]", style=f"dim {color}")
        result.append("\n\n")

        # Prompt
        if self.phase_prompt:
            result.append(self.phase_prompt, style="italic dim")
            result.append("\n")

        # Extract fields
        if self.extract_fields:
            result.append("\n")
            result.append("Will extract: ", style="dim")
            result.append(", ".join(self.extract_fields), style="dim cyan")

        return result

    def set_phase(
        self,
        name: str,
        prompt: str,
        status: str,
        step_num: int = 0,
        total_steps: int = 0,
        extract_fields: list[str] | None = None,
    ) -> None:
        """Update all phase data at once."""
        self.phase_name = name
        self.phase_prompt = prompt
        self.phase_status = status
        self.step_num = step_num
        self.total_steps = total_steps
        self.extract_fields = extract_fields or []
