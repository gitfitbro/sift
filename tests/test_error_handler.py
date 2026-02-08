"""Tests for the unified CLI error handler."""
import pytest
import typer
from sift.error_handler import handle_errors, _debug_mode
from sift.errors import SiftError, SessionNotFoundError


class TestHandleErrorsDecorator:
    def test_passes_through_on_success(self):
        @handle_errors
        def good_func():
            return "ok"

        assert good_func() == "ok"

    def test_catches_sift_error(self):
        @handle_errors
        def bad_func():
            raise SessionNotFoundError("missing")

        with pytest.raises(typer.Exit) as exc_info:
            bad_func()
        assert exc_info.value.exit_code == 1

    def test_catches_generic_sift_error(self):
        @handle_errors
        def bad_func():
            raise SiftError("generic issue")

        with pytest.raises(typer.Exit) as exc_info:
            bad_func()
        assert exc_info.value.exit_code == 1

    def test_catches_unexpected_error(self):
        @handle_errors
        def crash_func():
            raise RuntimeError("oops")

        with pytest.raises(typer.Exit) as exc_info:
            crash_func()
        assert exc_info.value.exit_code == 1

    def test_catches_keyboard_interrupt(self):
        @handle_errors
        def interrupted():
            raise KeyboardInterrupt()

        with pytest.raises(typer.Exit) as exc_info:
            interrupted()
        assert exc_info.value.exit_code == 130


class TestDebugMode:
    def test_debug_off_by_default(self, monkeypatch):
        monkeypatch.delenv("SIFT_DEBUG", raising=False)
        assert _debug_mode() is False

    def test_debug_on_with_1(self, monkeypatch):
        monkeypatch.setenv("SIFT_DEBUG", "1")
        assert _debug_mode() is True

    def test_debug_on_with_true(self, monkeypatch):
        monkeypatch.setenv("SIFT_DEBUG", "true")
        assert _debug_mode() is True

    def test_debug_off_with_0(self, monkeypatch):
        monkeypatch.setenv("SIFT_DEBUG", "0")
        assert _debug_mode() is False
