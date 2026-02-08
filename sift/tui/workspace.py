"""Workspace screen - session editor replacing workspace_cmd.open_workspace."""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Label, ListItem, ListView, Static

from sift.core.build_service import BuildService
from sift.core.extraction_service import ExtractionService
from sift.models import Session
from sift.tui.theme import ICONS
from sift.tui.widgets.capture_form import CaptureForm
from sift.tui.widgets.extraction_view import ExtractionView
from sift.tui.widgets.pipeline import PipelineWidget


class WorkspaceScreen(Screen):
    """Interactive workspace for browsing, editing, and rebuilding session data."""

    BINDINGS = [
        ("b", "browse", "Browse"),
        ("r", "rebuild", "Rebuild"),
        ("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, session_name: str, **kwargs):
        super().__init__(**kwargs)
        self.session_name = session_name
        self._extraction_svc = ExtractionService()
        self._build_svc = BuildService()
        self._session: Session | None = None
        self._template = None
        self._add_more_phase_id: str | None = None

    def compose(self):
        yield Header()
        yield PipelineWidget(id="pipeline")
        with VerticalScroll(id="workspace-container"):
            yield Static(id="session-info")
            yield Static("Select a phase to view details:", id="phase-prompt")
            yield ListView(id="phase-list")
            yield CaptureForm(id="capture-form")
            yield ExtractionView(id="extraction-view")
            yield Static(id="transcript-view")
        with Horizontal(id="action-bar"):
            yield Button("Add More", id="btn-add-more", variant="default")
            yield Button("Re-extract", id="btn-re-extract", variant="primary")
            yield Button("Rebuild Outputs", id="btn-rebuild", variant="warning")
            yield Button("Quit", id="btn-quit", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        self._load_session()

    def _load_session(self) -> None:
        """Load session data and populate UI."""
        try:
            self._session = Session.load(self.session_name)
        except FileNotFoundError:
            self.notify(f"Session '{self.session_name}' not found", severity="error")
            self.app.pop_screen()
            return

        self._template = self._session.get_template()
        self._refresh_ui()

    async def _refresh_ui(self) -> None:
        """Refresh all UI from session state."""
        if not self._session or not self._template:
            return

        self._session = Session.load(self.session_name)
        self.sub_title = f"Workspace: {self.session_name}"

        # Pipeline
        phase_list = []
        for pt in self._template.phases:
            ps = self._session.phases.get(pt.id)
            phase_list.append(
                {
                    "id": pt.id,
                    "name": pt.name,
                    "status": ps.status if ps else "pending",
                }
            )
        self.query_one("#pipeline", PipelineWidget).update_phases(phase_list)

        # Session info
        total = len(self._template.phases)
        done = sum(
            1 for p in self._session.phases.values() if p.status in ("extracted", "complete")
        )
        info = self.query_one("#session-info", Static)
        info.update(
            f"{self._template.name}  |  {done}/{total} phases complete  |  "
            f"Status: {self._session.status}"
        )

        # Phase list
        lv = self.query_one("#phase-list", ListView)
        await lv.clear()
        for pt in self._template.phases:
            ps = self._session.phases.get(pt.id)
            status = ps.status if ps else "pending"
            icon = ICONS.get(status, ICONS["pending"])
            lv.append(ListItem(Label(f"{icon}  {pt.name}  [{status}]"), id=f"phase-{pt.id}"))

        # Hide detail views initially
        self.query_one("#capture-form", CaptureForm).display = False
        self.query_one("#btn-add-more", Button).display = False
        self.query_one("#extraction-view", ExtractionView).display = False
        self.query_one("#transcript-view", Static).display = False

    @on(ListView.Selected, "#phase-list")
    def phase_selected(self, event: ListView.Selected) -> None:
        """Show details for the selected phase."""
        item_id = event.item.id or ""
        phase_id = item_id.replace("phase-", "")
        if not phase_id or not self._session:
            return

        pt = next((p for p in self._template.phases if p.id == phase_id), None)
        if not pt:
            return

        # Hide capture form when switching phases
        self.query_one("#capture-form", CaptureForm).display = False
        self._add_more_phase_id = None

        # Show transcript
        transcript_view = self.query_one("#transcript-view", Static)
        transcript = self._session.get_transcript(phase_id)
        if transcript:
            preview = transcript[:1000]
            if len(transcript) > 1000:
                preview += f"\n\n... ({len(transcript):,} total chars)"
            transcript_view.update(f"--- Transcript: {pt.name} ---\n\n{preview}")
            transcript_view.display = True
        else:
            transcript_view.update(f"No transcript for {pt.name}")
            transcript_view.display = True

        # Show extraction
        extraction_view = self.query_one("#extraction-view", ExtractionView)
        extracted = self._session.get_extracted(phase_id)
        if extracted:
            extraction_view.load_data(extracted, pt.name)
            extraction_view.display = True
        else:
            extraction_view.display = False

        # Show "Add More" button for phases that have content
        ps = self._session.phases.get(phase_id)
        has_content = ps and ps.status not in ("pending",)
        self.query_one("#btn-add-more", Button).display = bool(has_content)

    @on(Button.Pressed, "#btn-add-more")
    def handle_add_more(self) -> None:
        """Show capture form to append content to the selected phase."""
        lv = self.query_one("#phase-list", ListView)
        if lv.highlighted_child is None:
            self.notify("Select a phase first", severity="warning")
            return

        item_id = lv.highlighted_child.id or ""
        phase_id = item_id.replace("phase-", "")
        self._add_more_phase_id = phase_id
        self.query_one("#capture-form", CaptureForm).display = True
        self.query_one("#btn-add-more", Button).display = False

    @on(CaptureForm.Submitted)
    def handle_capture(self, event: CaptureForm.Submitted) -> None:
        """Handle capture form submission in workspace (always appends)."""
        phase_id = self._add_more_phase_id
        if not phase_id:
            return
        self._add_more_phase_id = None

        if event.mode == "text":
            self._do_add_text(phase_id, event.content)
        elif event.mode == "file":
            self._do_add_file(phase_id, event.content)

    @on(CaptureForm.Skipped)
    def handle_skip(self, event: CaptureForm.Skipped) -> None:
        """Cancel add-more."""
        self._add_more_phase_id = None
        self.query_one("#capture-form", CaptureForm).display = False

    @work(thread=True)
    def _do_add_text(self, phase_id: str, text: str) -> None:
        """Append text in a worker thread."""
        try:
            result = self._extraction_svc.capture_text(
                self.session_name, phase_id, text, append=True
            )
            label = "appended" if result.appended else "captured"
            self.app.call_from_thread(
                self.notify, f"Text {label} ({result.char_count} chars)", severity="information"
            )
        except Exception as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")
        self.app.call_from_thread(self._refresh_ui)

    @work(thread=True)
    def _do_add_file(self, phase_id: str, file_path: str) -> None:
        """Append file content in a worker thread."""
        try:
            result = self._extraction_svc.capture_file(
                self.session_name, phase_id, Path(file_path), append=True
            )
            label = "appended" if result.appended else "captured"
            self.app.call_from_thread(
                self.notify, f"File {label} ({result.file_type})", severity="information"
            )
        except Exception as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")
        self.app.call_from_thread(self._refresh_ui)

    @on(Button.Pressed, "#btn-re-extract")
    def handle_re_extract(self) -> None:
        """Re-extract the selected phase."""
        lv = self.query_one("#phase-list", ListView)
        if lv.highlighted_child is None:
            self.notify("Select a phase first", severity="warning")
            return

        item_id = lv.highlighted_child.id or ""
        phase_id = item_id.replace("phase-", "")
        ps = self._session.phases.get(phase_id) if self._session else None
        if not ps or ps.status not in ("transcribed", "extracted", "complete"):
            self.notify("Phase needs a transcript before extraction", severity="warning")
            return

        self._do_re_extract(phase_id)

    @work(thread=True)
    def _do_re_extract(self, phase_id: str) -> None:
        """Re-extract in a worker thread."""
        self.app.call_from_thread(self.notify, "Re-extracting...", severity="information")
        try:
            result = self._extraction_svc.extract_phase(self.session_name, phase_id)
            self.app.call_from_thread(
                self.notify,
                f"Re-extracted {result.field_count} fields",
                severity="information",
            )
        except Exception as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")
        self.app.call_from_thread(self._refresh_ui)

    @on(Button.Pressed, "#btn-rebuild")
    def _on_rebuild_button(self) -> None:
        """Rebuild all outputs."""
        self._do_rebuild()

    @work(thread=True)
    def _do_rebuild(self) -> None:
        """Rebuild in a worker thread."""
        self.app.call_from_thread(self.notify, "Rebuilding outputs...", severity="information")
        try:
            result = self._build_svc.generate_outputs(self.session_name, "all")
            files = ", ".join(label for label, _ in result.generated_files)
            self.app.call_from_thread(
                self.notify,
                f"Generated: {files}",
                severity="information",
                timeout=8,
            )
        except Exception as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")

    @on(Button.Pressed, "#btn-quit")
    def handle_quit(self) -> None:
        """Close workspace."""
        self.app.pop_screen()

    def action_browse(self) -> None:
        """Focus the phase list for browsing."""
        self.query_one("#phase-list", ListView).focus()

    def action_rebuild(self) -> None:
        """Trigger rebuild."""
        self._do_rebuild()
