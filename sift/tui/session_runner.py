"""Session runner screen - guided walkthrough replacing interactive.py."""

from __future__ import annotations

from pathlib import Path

from textual import on, work
from textual.containers import Horizontal, VerticalScroll
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Static

from sift.core.build_service import BuildService
from sift.core.extraction_service import ExtractionService
from sift.models import Session
from sift.tui.theme import ICONS
from sift.tui.widgets.capture_form import CaptureForm
from sift.tui.widgets.extraction_view import ExtractionView
from sift.tui.widgets.phase_panel import PhasePanel
from sift.tui.widgets.pipeline import PipelineWidget


class SessionRunnerScreen(Screen):
    """Guided walkthrough for a session, phase by phase."""

    BINDINGS = [
        ("n", "next_phase", "Next Phase"),
        ("escape", "app.pop_screen", "Back"),
    ]

    def __init__(self, session_name: str, start_phase: str | None = None, **kwargs):
        super().__init__(**kwargs)
        self.session_name = session_name
        self.start_phase = start_phase
        self._extraction_svc = ExtractionService()
        self._build_svc = BuildService()
        self._current_phase_idx = 0
        self._session: Session | None = None
        self._template = None
        self._phases: list = []
        self._appending = False

    def compose(self):
        yield Header()
        yield PipelineWidget(id="pipeline")
        with VerticalScroll(id="runner-container"):
            yield PhasePanel(id="phase-panel")
            yield Static(id="status-msg")
            yield CaptureForm(id="capture-form")
            yield ExtractionView(id="extraction-view")
            with Horizontal(id="action-buttons"):
                yield Button("Extract", id="btn-extract", variant="primary")
                yield Button("Add More", id="btn-add-more", variant="default")
                yield Button("Next Phase", id="btn-next", variant="success")
                yield Button("Generate Outputs", id="btn-build", variant="warning")
                yield Button("Done – Exit", id="btn-done", variant="success")
        yield Footer()

    def on_mount(self) -> None:
        self._load_session()

    def _load_session(self) -> None:
        """Load session and template, find starting phase."""
        try:
            self._session = Session.load(self.session_name)
        except FileNotFoundError:
            self.notify(f"Session '{self.session_name}' not found", severity="error")
            self.app.pop_screen()
            return

        self._template = self._session.get_template()
        self._phases = list(self._template.phases)

        # Find starting point
        if self.start_phase:
            for i, p in enumerate(self._phases):
                if p.id == self.start_phase:
                    self._current_phase_idx = i
                    break
        else:
            # Start at first incomplete phase
            for i, pt in enumerate(self._phases):
                ps = self._session.phases.get(pt.id)
                if not ps or ps.status not in ("extracted", "complete"):
                    self._current_phase_idx = i
                    break

        self._refresh_ui()

    def _refresh_ui(self) -> None:
        """Refresh all UI elements from current state."""
        if not self._session or not self._template:
            return

        # Reload session
        self._session = Session.load(self.session_name)

        # Update pipeline
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

        current_pt = (
            self._phases[self._current_phase_idx]
            if self._current_phase_idx < len(self._phases)
            else None
        )
        pipeline = self.query_one("#pipeline", PipelineWidget)
        pipeline.update_phases(phase_list, current_pt.id if current_pt else "")

        # Update header
        self.sub_title = f"{self._template.name} - {self.session_name}"

        if not current_pt:
            self._show_completion()
            return

        ps = self._session.phases.get(current_pt.id)
        status = ps.status if ps else "pending"

        # Update phase panel
        panel = self.query_one("#phase-panel", PhasePanel)
        panel.set_phase(
            name=current_pt.name,
            prompt=current_pt.prompt.strip(),
            status=status,
            step_num=self._current_phase_idx + 1,
            total_steps=len(self._phases),
            extract_fields=[e.id for e in current_pt.extract] if current_pt.extract else [],
        )

        # Show/hide widgets based on phase status
        capture_form = self.query_one("#capture-form", CaptureForm)
        extract_btn = self.query_one("#btn-extract", Button)
        add_more_btn = self.query_one("#btn-add-more", Button)
        next_btn = self.query_one("#btn-next", Button)
        build_btn = self.query_one("#btn-build", Button)
        done_btn = self.query_one("#btn-done", Button)
        extraction_view = self.query_one("#extraction-view", ExtractionView)
        status_msg = self.query_one("#status-msg", Static)

        if status == "pending":
            capture_form.display = True
            extract_btn.display = False
            add_more_btn.display = False
            next_btn.display = False
            build_btn.display = False
            done_btn.display = False
            extraction_view.display = False
            status_msg.update("")
        elif status == "transcribed":
            capture_form.display = False
            extract_btn.display = True
            add_more_btn.display = True
            next_btn.display = False
            build_btn.display = False
            done_btn.display = False
            extraction_view.display = False
            status_msg.update(f"{ICONS['transcribed']} Transcript captured. Ready to extract.")
        elif status in ("extracted", "complete"):
            capture_form.display = False
            extract_btn.display = False
            add_more_btn.display = True
            build_btn.display = False
            done_btn.display = False
            extraction_view.display = True

            # Load extracted data
            extracted = self._session.get_extracted(current_pt.id)
            extraction_view.load_data(extracted or {}, current_pt.name)

            # Show next button if there are more phases
            has_more = self._current_phase_idx < len(self._phases) - 1
            all_done = all(
                self._session.phases.get(p.id)
                and self._session.phases[p.id].status in ("extracted", "complete")
                for p in self._phases
            )
            next_btn.display = has_more
            build_btn.display = all_done
            status_msg.update(f"{ICONS['complete']} Extraction complete.")
        elif status == "captured":
            capture_form.display = False
            extract_btn.display = False
            add_more_btn.display = False
            next_btn.display = False
            build_btn.display = False
            done_btn.display = False
            extraction_view.display = False
            status_msg.update(f"{ICONS['captured']} Audio captured. Transcription needed.")

    def _show_completion(self) -> None:
        """Show completion state when all phases done."""
        capture_form = self.query_one("#capture-form", CaptureForm)
        extract_btn = self.query_one("#btn-extract", Button)
        add_more_btn = self.query_one("#btn-add-more", Button)
        next_btn = self.query_one("#btn-next", Button)
        build_btn = self.query_one("#btn-build", Button)
        done_btn = self.query_one("#btn-done", Button)
        status_msg = self.query_one("#status-msg", Static)

        capture_form.display = False
        extract_btn.display = False
        add_more_btn.display = False
        next_btn.display = False
        build_btn.display = True
        done_btn.display = False
        status_msg.update(f"{ICONS['complete']} All phases complete! Generate outputs?")

    @on(Button.Pressed, "#btn-add-more")
    def handle_add_more(self) -> None:
        """Show capture form in append mode for the current phase."""
        self._appending = True
        capture_form = self.query_one("#capture-form", CaptureForm)
        extraction_view = self.query_one("#extraction-view", ExtractionView)
        add_more_btn = self.query_one("#btn-add-more", Button)
        capture_form.display = True
        extraction_view.display = False
        add_more_btn.display = False

    @on(CaptureForm.Submitted)
    def handle_capture(self, event: CaptureForm.Submitted) -> None:
        """Handle capture form submission."""
        current_pt = self._phases[self._current_phase_idx]
        append = self._appending
        self._appending = False

        if event.mode == "text":
            self._do_capture_text(current_pt.id, event.content, append)
        elif event.mode == "file":
            self._do_capture_file(current_pt.id, event.content, append)

    @work(thread=True)
    def _do_capture_text(self, phase_id: str, text: str, append: bool = False) -> None:
        """Capture text in a worker thread."""
        try:
            result = self._extraction_svc.capture_text(
                self.session_name, phase_id, text, append=append
            )
            label = "appended" if result.appended else "captured"
            self.app.call_from_thread(
                self.notify, f"Text {label} ({result.char_count} chars)", severity="information"
            )
        except Exception as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")
        self.app.call_from_thread(self._refresh_ui)

    @work(thread=True)
    def _do_capture_file(self, phase_id: str, file_path: str, append: bool = False) -> None:
        """Capture file in a worker thread."""
        try:
            result = self._extraction_svc.capture_file(
                self.session_name, phase_id, Path(file_path), append=append
            )
            label = "appended" if result.appended else "captured"
            self.app.call_from_thread(
                self.notify, f"File {label} ({result.file_type})", severity="information"
            )
        except Exception as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")
        self.app.call_from_thread(self._refresh_ui)

    @on(CaptureForm.Skipped)
    def handle_skip(self, event: CaptureForm.Skipped) -> None:
        """Handle capture skip."""
        self.notify("Phase skipped", severity="warning")
        self.action_next_phase()

    @on(Button.Pressed, "#btn-extract")
    def handle_extract(self) -> None:
        """Run extraction on current phase."""
        current_pt = self._phases[self._current_phase_idx]
        self._do_extract(current_pt.id)

    @work(thread=True)
    def _do_extract(self, phase_id: str) -> None:
        """Extract in a worker thread."""
        self.app.call_from_thread(self.notify, "Extracting...", severity="information")
        try:
            result = self._extraction_svc.extract_phase(self.session_name, phase_id)
            self.app.call_from_thread(
                self.notify,
                f"Extracted {result.field_count} fields",
                severity="information",
            )
        except Exception as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")
        self.app.call_from_thread(self._refresh_ui)

    @on(Button.Pressed, "#btn-next")
    def action_next_phase(self) -> None:
        """Move to the next phase."""
        if self._current_phase_idx < len(self._phases) - 1:
            self._current_phase_idx += 1
            self._refresh_ui()
        else:
            self._show_completion()

    @on(Button.Pressed, "#btn-build")
    def handle_build(self) -> None:
        """Generate outputs."""
        self._do_build()

    @work(thread=True)
    def _do_build(self) -> None:
        """Build outputs in a worker thread."""
        self.app.call_from_thread(self.notify, "Generating outputs...", severity="information")
        try:
            result = self._build_svc.generate_outputs(self.session_name, "all")
            files = ", ".join(label for label, _ in result.generated_files)
            self.app.call_from_thread(
                self.notify,
                f"Generated: {files}",
                severity="information",
                timeout=8,
            )
            self.app.call_from_thread(self._show_build_complete, files)
        except Exception as e:
            self.app.call_from_thread(self.notify, str(e), severity="error")

    def _show_build_complete(self, files: str) -> None:
        """Update UI to show build-complete state with a clear exit path."""
        build_btn = self.query_one("#btn-build", Button)
        done_btn = self.query_one("#btn-done", Button)
        status_msg = self.query_one("#status-msg", Static)

        build_btn.display = False
        done_btn.display = True
        status_msg.update(
            f"{ICONS['complete']} All done! Generated: {files}\n"
            f"Press Done to exit, or q to quit."
        )

    @on(Button.Pressed, "#btn-done")
    def handle_done(self) -> None:
        """Exit the app cleanly after build."""
        self.app.exit()
