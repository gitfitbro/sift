"""Tests for the sift doctor diagnostic command."""

from typer.testing import CliRunner

from sift.cli import app

runner = CliRunner()


class TestDoctorCommand:
    def test_doctor_runs(self):
        result = runner.invoke(app, ["doctor"])
        assert "Python version" in result.output
        assert "Data directory" in result.output

    def test_doctor_shows_providers(self):
        result = runner.invoke(app, ["doctor"])
        assert "Provider:" in result.output

    def test_doctor_shows_optional_deps(self):
        result = runner.invoke(app, ["doctor"])
        assert "Optional:" in result.output

    def test_doctor_verbose(self):
        result = runner.invoke(app, ["doctor", "--verbose"])
        assert "Python version" in result.output
