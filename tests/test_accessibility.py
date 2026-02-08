"""Tests for accessibility features: plain mode and JSON output."""

import json
import pytest
from io import StringIO

import sift.ui as ui


@pytest.fixture(autouse=True)
def reset_ui_modes():
    """Reset UI modes before and after each test."""
    ui.set_plain_mode(False)
    ui.set_json_mode(False)
    # Re-create console with theme after reset
    from rich.console import Console
    ui.console = Console(theme=ui.SIFT_THEME)
    yield
    ui.set_plain_mode(False)
    ui.set_json_mode(False)
    ui.console = Console(theme=ui.SIFT_THEME)


class TestPlainMode:
    """Test plain text output mode."""

    def test_set_plain_mode(self):
        ui.set_plain_mode(True)
        assert ui.is_plain() is True

    def test_plain_mode_off_by_default(self):
        assert ui.is_plain() is False

    def test_plain_icons(self):
        ui.set_plain_mode(True)
        assert ui.phase_status_icon("complete") == "[OK]"
        assert ui.phase_status_icon("active") == "[>>]"
        assert ui.phase_status_icon("pending") == "[ ]"
        assert ui.phase_status_icon("error") == "[!!]"

    def test_rich_icons_by_default(self):
        icon = ui.phase_status_icon("complete")
        assert "[green]" in icon

    def test_plain_banner(self, capsys):
        ui.set_plain_mode(True)
        ui.banner()
        captured = capsys.readouterr()
        assert "sift" in captured.out
        assert "[bold" not in captured.out

    def test_plain_step_header(self, capsys):
        ui.set_plain_mode(True)
        ui.step_header(1, 3, "Test Step", "Subtitle")
        captured = capsys.readouterr()
        assert "Step 1/3" in captured.out
        assert "Test Step" in captured.out
        assert "Subtitle" in captured.out

    def test_plain_success_panel(self, capsys):
        ui.set_plain_mode(True)
        ui.success_panel("Done!", "It worked")
        captured = capsys.readouterr()
        assert "OK: Done!" in captured.out
        assert "It worked" in captured.out

    def test_plain_error_panel(self, capsys):
        ui.set_plain_mode(True)
        ui.error_panel("Failed!", "Something broke")
        captured = capsys.readouterr()
        assert "ERROR: Failed!" in captured.err

    def test_plain_section_divider(self, capsys):
        ui.set_plain_mode(True)
        ui.section_divider("Section")
        captured = capsys.readouterr()
        assert "-- Section --" in captured.out

    def test_plain_format_next_step(self, capsys):
        ui.set_plain_mode(True)
        ui.format_next_step("sift run test")
        captured = capsys.readouterr()
        assert "Next: sift run test" in captured.out

    def test_plain_pipeline_view(self, capsys):
        ui.set_plain_mode(True)
        phases = [
            {"id": "a", "name": "Phase A", "status": "complete"},
            {"id": "b", "name": "Phase B", "status": "pending"},
        ]
        ui.pipeline_view(phases, current_phase="b")
        captured = capsys.readouterr()
        assert "[OK] Phase A" in captured.out
        assert "Phase B" in captured.out
        assert "<-- current" in captured.out


class TestJsonMode:
    """Test JSON output mode."""

    def test_set_json_mode(self):
        ui.set_json_mode(True)
        assert ui.is_json() is True

    def test_json_mode_off_by_default(self):
        assert ui.is_json() is False

    def test_json_banner_suppressed(self, capsys):
        ui.set_json_mode(True)
        ui.banner()
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_json_step_header_suppressed(self, capsys):
        ui.set_json_mode(True)
        ui.step_header(1, 3, "Test", "Sub")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_json_pipeline_view(self, capsys):
        ui.set_json_mode(True)
        ui.set_plain_mode(True)
        phases = [
            {"id": "a", "name": "Phase A", "status": "complete"},
            {"id": "b", "name": "Phase B", "status": "pending"},
        ]
        ui.pipeline_view(phases, current_phase="b")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert len(data) == 2
        assert data[0]["id"] == "a"
        assert data[0]["current"] is False
        assert data[1]["current"] is True

    def test_json_error_panel(self, capsys):
        ui.set_json_mode(True)
        ui.set_plain_mode(True)
        ui.error_panel("Oops", "Details here")
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["error"] == "Oops"
        assert data["detail"] == "Details here"

    def test_print_json_output(self, capsys):
        ui.print_json_output({"key": "value", "num": 42})
        captured = capsys.readouterr()
        data = json.loads(captured.out)
        assert data["key"] == "value"
        assert data["num"] == 42

    def test_json_section_divider_suppressed(self, capsys):
        ui.set_json_mode(True)
        ui.section_divider("Test")
        captured = capsys.readouterr()
        assert captured.out == ""

    def test_json_format_next_step_suppressed(self, capsys):
        ui.set_json_mode(True)
        ui.format_next_step("sift test")
        captured = capsys.readouterr()
        assert captured.out == ""
