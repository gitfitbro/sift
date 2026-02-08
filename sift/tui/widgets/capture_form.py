"""Capture form widget - file path, text input, or project analysis for phase capture."""

from __future__ import annotations

from pathlib import Path

from textual import on
from textual.containers import Horizontal, Vertical
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Button, Input, Static, TextArea


class CaptureForm(Widget):
    """Form for capturing phase content (text input, file path, or project analysis)."""

    class Submitted(Message):
        """Fired when the user submits capture data."""

        def __init__(self, mode: str, content: str) -> None:
            super().__init__()
            self.mode = mode  # "text", "file", or "analyze"
            self.content = content

    class Skipped(Message):
        """Fired when the user skips capture."""

    mode: reactive[str] = reactive("text")  # "text", "file", or "analyze"

    def compose(self):
        with Vertical():
            yield Static("How do you want to capture this phase?", classes="form-label")
            with Horizontal():
                yield Button("Text Input", id="btn-text", variant="primary")
                yield Button("File Upload", id="btn-file", variant="default")
                yield Button("Analyze Project", id="btn-analyze", variant="default")
                yield Button("Skip", id="btn-skip", variant="warning")

            # Text mode
            yield TextArea(id="text-input", language=None)
            yield Button("Submit Text", id="btn-submit-text", variant="success")

            # File mode
            yield Input(placeholder="Enter file path...", id="file-input")
            yield Button("Submit File", id="btn-submit-file", variant="success")

            # Analyze mode
            yield Input(placeholder="Enter project directory path...", id="analyze-input")
            yield Button("Run Analysis", id="btn-submit-analyze", variant="success")

    def on_mount(self) -> None:
        self._update_mode_visibility()

    def _update_mode_visibility(self) -> None:
        text_area = self.query_one("#text-input", TextArea)
        submit_text = self.query_one("#btn-submit-text", Button)
        file_input = self.query_one("#file-input", Input)
        submit_file = self.query_one("#btn-submit-file", Button)
        analyze_input = self.query_one("#analyze-input", Input)
        submit_analyze = self.query_one("#btn-submit-analyze", Button)

        text_area.display = self.mode == "text"
        submit_text.display = self.mode == "text"
        file_input.display = self.mode == "file"
        submit_file.display = self.mode == "file"
        analyze_input.display = self.mode == "analyze"
        submit_analyze.display = self.mode == "analyze"

    @on(Button.Pressed, "#btn-text")
    def switch_text_mode(self) -> None:
        self.mode = "text"
        self._update_mode_visibility()

    @on(Button.Pressed, "#btn-file")
    def switch_file_mode(self) -> None:
        self.mode = "file"
        self._update_mode_visibility()

    @on(Button.Pressed, "#btn-analyze")
    def switch_analyze_mode(self) -> None:
        self.mode = "analyze"
        self._update_mode_visibility()

    @on(Button.Pressed, "#btn-skip")
    def skip_capture(self) -> None:
        self.post_message(self.Skipped())

    @on(Button.Pressed, "#btn-submit-text")
    def submit_text(self) -> None:
        text_area = self.query_one("#text-input", TextArea)
        text = text_area.text.strip()
        if text:
            self.post_message(self.Submitted(mode="text", content=text))
        else:
            self.notify("Please enter some text", severity="warning")

    @on(Button.Pressed, "#btn-submit-file")
    def submit_file(self) -> None:
        file_input = self.query_one("#file-input", Input)
        path_str = file_input.value.strip()
        if not path_str:
            self.notify("Please enter a file path", severity="warning")
            return
        path = Path(path_str)
        if not path.exists():
            self.notify(f"File not found: {path}", severity="error")
            return
        self.post_message(self.Submitted(mode="file", content=str(path)))

    @on(Button.Pressed, "#btn-submit-analyze")
    def submit_analyze(self) -> None:
        analyze_input = self.query_one("#analyze-input", Input)
        path_str = analyze_input.value.strip()
        if not path_str:
            self.notify("Please enter a project path", severity="warning")
            return
        path = Path(path_str)
        if not path.is_dir():
            self.notify(f"Not a directory: {path}", severity="error")
            return
        self.post_message(self.Submitted(mode="analyze", content=str(path)))
