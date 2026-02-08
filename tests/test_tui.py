"""Tests for sift TUI components to prevent runtime regressions."""

from __future__ import annotations

import pytest
from rich.text import Text
from textual.color import Color


class TestThemeColors:
    """Verify all theme colors are parseable by Textual's color engine."""

    def test_status_colors_all_valid(self):
        """Every STATUS_COLORS value must be parseable by Textual."""
        from sift.tui.theme import STATUS_COLORS

        for status, color_str in STATUS_COLORS.items():
            try:
                Color.parse(color_str)
            except Exception as e:
                pytest.fail(
                    f"STATUS_COLORS['{status}'] = '{color_str}' is not a valid Textual color: {e}"
                )

    def test_fallback_colors_valid(self):
        """Fallback color values used in widgets must be valid."""
        fallbacks = ["#808080"]  # used in pipeline.py and phase_panel.py
        for color_str in fallbacks:
            try:
                Color.parse(color_str)
            except Exception as e:
                pytest.fail(f"Fallback color '{color_str}' is not valid: {e}")

    def test_inline_style_colors_valid(self):
        """Colors used in Rich Text style= arguments must render without error."""
        from sift.tui.theme import STATUS_COLORS

        for _status, color_str in STATUS_COLORS.items():
            # These patterns match how colors are used in pipeline.py and phase_panel.py
            text1 = Text("test", style=color_str)
            assert text1.plain == "test"

            text2 = Text("test", style=f"dim {color_str}")
            assert text2.plain == "test"

            text3 = Text("test", style=f"bold {color_str}")
            assert text3.plain == "test"

    def test_no_camel_case_colors(self):
        """Ensure no camelCase color names sneak in (Textual doesn't support them)."""
        import re

        from sift.tui.theme import STATUS_COLORS

        camel_pattern = re.compile(r"[a-z][A-Z]")
        for status, color_str in STATUS_COLORS.items():
            assert not camel_pattern.search(color_str), (
                f"STATUS_COLORS['{status}'] = '{color_str}' contains camelCase. "
                f"Use hex codes or underscored names for Textual compatibility."
            )


class TestSiftAppInit:
    """Verify SiftApp can be constructed without an event loop."""

    def test_app_creates_without_event_loop(self):
        """SiftApp() must not call push_screen during __init__."""
        from sift.tui.app import SiftApp

        app = SiftApp("test-session", start_phase="phase-1")
        assert app.session_name == "test-session"
        assert app._start_phase == "phase-1"

    def test_app_creates_without_session(self):
        """SiftApp() with no session should work (no screen push)."""
        from sift.tui.app import SiftApp

        app = SiftApp()
        assert app.session_name is None
        assert app._start_phase is None


class TestPipelineWidget:
    """Test PipelineWidget renders without errors."""

    def test_render_empty(self):
        from sift.tui.widgets.pipeline import PipelineWidget

        w = PipelineWidget()
        result = w.render()
        assert isinstance(result, Text)
        assert "No phases" in result.plain

    def test_render_with_phases(self):
        from sift.tui.widgets.pipeline import PipelineWidget

        phases = [
            {"id": "p1", "name": "Phase 1", "status": "complete"},
            {"id": "p2", "name": "Phase 2", "status": "active"},
            {"id": "p3", "name": "Phase 3", "status": "pending"},
            {"id": "p4", "name": "Phase 4", "status": "transcribed"},
            {"id": "p5", "name": "Phase 5", "status": "captured"},
        ]
        w = PipelineWidget(phases=phases, current_phase="p2")
        result = w.render()
        assert isinstance(result, Text)
        assert "Phase 1" in result.plain
        assert "Phase 2" in result.plain

    def test_render_unknown_status_uses_fallback(self):
        """Unknown status should use fallback color, not crash."""
        from sift.tui.widgets.pipeline import PipelineWidget

        phases = [{"id": "p1", "name": "Test", "status": "unknown_status"}]
        w = PipelineWidget(phases=phases)
        result = w.render()
        assert isinstance(result, Text)
        assert "Test" in result.plain


class TestPhasePanelWidget:
    """Test PhasePanel renders without errors."""

    def test_render_default(self):
        from sift.tui.widgets.phase_panel import PhasePanel

        w = PhasePanel()
        result = w.render()
        assert isinstance(result, Text)

    def test_render_all_statuses(self):
        """Rendering every known status must not crash."""
        from sift.tui.theme import STATUS_COLORS
        from sift.tui.widgets.phase_panel import PhasePanel

        for status in STATUS_COLORS:
            w = PhasePanel()
            w.phase_name = f"Test {status}"
            w.phase_prompt = "Do something"
            w.phase_status = status
            w.step_num = 1
            w.total_steps = 5
            w.extract_fields = ["field_a", "field_b"]
            result = w.render()
            assert isinstance(result, Text)
            assert f"Test {status}" in result.plain


class TestExtractionView:
    """Test ExtractionView widget."""

    def test_init(self):
        from sift.tui.widgets.extraction_view import ExtractionView

        view = ExtractionView()
        assert view.show_header is True
        assert view.zebra_stripes is True


class TestCaptureForm:
    """Test CaptureForm widget construction."""

    def test_init(self):
        from sift.tui.widgets.capture_form import CaptureForm

        form = CaptureForm()
        assert form.mode == "text"


class TestSessionRunnerScreen:
    """Test SessionRunnerScreen construction and methods."""

    def test_compose_includes_done_button(self):
        """The Done button must exist in the compose method source."""
        import inspect

        from sift.tui.session_runner import SessionRunnerScreen

        source = inspect.getsource(SessionRunnerScreen.compose)
        assert 'id="btn-done"' in source, (
            "btn-done not found in SessionRunnerScreen.compose(). "
            "The Done button must exist so users can exit after build."
        )

    def test_show_build_complete_method_exists(self):
        """_show_build_complete must be defined for post-build flow."""
        from sift.tui.session_runner import SessionRunnerScreen

        screen = SessionRunnerScreen("test-session")
        assert hasattr(screen, "_show_build_complete")
        assert callable(screen._show_build_complete)

    def test_handle_done_method_exists(self):
        """handle_done must be defined so the Done button works."""
        from sift.tui.session_runner import SessionRunnerScreen

        screen = SessionRunnerScreen("test-session")
        assert hasattr(screen, "handle_done")
        assert callable(screen.handle_done)
