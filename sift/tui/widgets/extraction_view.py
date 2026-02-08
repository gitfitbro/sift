"""Extraction view widget - displays extracted data in a table."""
from __future__ import annotations

from textual.widgets import DataTable
from textual.reactive import reactive


class ExtractionView(DataTable):
    """Displays extracted phase data as a table."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.show_header = True
        self.zebra_stripes = True

    def on_mount(self) -> None:
        self.add_columns("Field", "Value")

    def load_data(self, extracted: dict, phase_name: str = "") -> None:
        """Load extracted data into the table."""
        self.clear()

        if not extracted:
            self.add_row("(no data)", "", key="empty")
            return

        for field_id, value in extracted.items():
            if field_id.startswith("_"):
                continue

            display_name = field_id.replace("_", " ").title()

            if isinstance(value, list):
                if value:
                    display = "\n".join(
                        f"\u2022 {item}" if not isinstance(item, dict)
                        else "\u2022 " + ", ".join(f"{k}: {v}" for k, v in item.items())
                        for item in value[:8]
                    )
                    if len(value) > 8:
                        display += f"\n... and {len(value) - 8} more"
                else:
                    display = "(none)"
            elif isinstance(value, dict):
                display = "\n".join(f"{k}: {v}" for k, v in list(value.items())[:8])
                if len(value) > 8:
                    display += f"\n... and {len(value) - 8} more"
            else:
                display = str(value)[:300]
                if len(str(value)) > 300:
                    display += "..."

            self.add_row(display_name, display, key=field_id)
