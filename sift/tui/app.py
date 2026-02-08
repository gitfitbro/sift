"""Main Sift Textual application."""
from __future__ import annotations

from pathlib import Path
from textual.app import App


class SiftApp(App):
    """Sift TUI application."""

    TITLE = "sift"
    CSS_PATH = "sift.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("question_mark", "help", "Help"),
    ]

    def __init__(self, session_name: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.session_name = session_name

    def action_help(self) -> None:
        """Show help."""
        self.notify(
            "q=quit | Tab=navigate | Enter=select | Esc=back",
            title="Keyboard Shortcuts",
            timeout=5,
        )
