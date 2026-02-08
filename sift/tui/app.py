"""Main Sift Textual application."""

from __future__ import annotations

from textual.app import App


class SiftApp(App):
    """Sift TUI application."""

    TITLE = "sift"
    CSS_PATH = "sift.tcss"

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("question_mark", "help", "Help"),
    ]

    def __init__(
        self,
        session_name: str | None = None,
        start_phase: str | None = None,
        mode: str = "run",
        **kwargs,
    ):
        super().__init__(**kwargs)
        self.session_name = session_name
        self._start_phase = start_phase
        self._mode = mode

    def on_mount(self) -> None:
        """Push the appropriate screen once the event loop is running."""
        if self.session_name is None:
            return

        if self._mode == "workspace":
            from sift.tui.workspace import WorkspaceScreen

            self.push_screen(WorkspaceScreen(self.session_name))
        else:
            from sift.tui.session_runner import SessionRunnerScreen

            self.push_screen(SessionRunnerScreen(self.session_name, start_phase=self._start_phase))

    def action_help(self) -> None:
        """Show help."""
        self.notify(
            "q=quit | Tab=navigate | Enter=select | Esc=back",
            title="Keyboard Shortcuts",
            timeout=5,
        )
