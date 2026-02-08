"""Capture form widget - file path or text input for phase capture."""
from __future__ import annotations

from pathlib import Path

from textual import on
from textual.widget import Widget
from textual.widgets import Button, Input, TextArea, Static
from textual.containers import Vertical, Horizontal
from textual.message import Message
from textual.reactive import reactive


class CaptureForm(Widget):
    """Form for capturing phase content (text input or file path)."""

    class Submitted(Message):
        """Fired when the user submits capture data."""
        def __init__(self, mode: str, content: str) -> None:
            super().__init__()
            self.mode = mode      # "text" or "file"
            self.content = content

    class Skipped(Message):
        """Fired when the user skips capture."""

    mode: reactive[str] = reactive("text")  # "text" or "file"

    def compose(self):
        with Vertical():
            yield Static("How do you want to capture this phase?", classes="form-label")
            with Horizontal():
                yield Button("Text Input", id="btn-text", variant="primary")
                yield Button("File Upload", id="btn-file", variant="default")
                yield Button("Skip", id="btn-skip", variant="warning")

            # Text mode
            yield TextArea(id="text-input", language=None)
            yield Button("Submit Text", id="btn-submit-text", variant="success")

            # File mode
            yield Input(placeholder="Enter file path...", id="file-input")
            yield Button("Submit File", id="btn-submit-file", variant="success")

    def on_mount(self) -> None:
        self._update_mode_visibility()

    def _update_mode_visibility(self) -> None:
        text_area = self.query_one("#text-input", TextArea)
        submit_text = self.query_one("#btn-submit-text", Button)
        file_input = self.query_one("#file-input", Input)
        submit_file = self.query_one("#btn-submit-file", Button)

        if self.mode == "text":
            text_area.display = True
            submit_text.display = True
            file_input.display = False
            submit_file.display = False
        else:
            text_area.display = False
            submit_text.display = False
            file_input.display = True
            submit_file.display = True

    @on(Button.Pressed, "#btn-text")
    def switch_text_mode(self) -> None:
        self.mode = "text"
        self._update_mode_visibility()

    @on(Button.Pressed, "#btn-file")
    def switch_file_mode(self) -> None:
        self.mode = "file"
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
