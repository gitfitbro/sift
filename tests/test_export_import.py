"""Tests for the export/import service."""

from __future__ import annotations

import json
import zipfile

import pytest
import yaml

from sift.core.export_service import ExportResult, ExportService, ImportResult


@pytest.fixture
def session_with_data(sample_template_path, sift_home):
    """Create a session with transcript and extracted data."""
    from sift.core.session_service import SessionService

    svc = SessionService()
    detail = svc.create_session("test-template", name="export-test")

    # Write a transcript
    from sift.models import Session

    session = Session.load("export-test")
    phase_id = list(session.phases.keys())[0]

    transcript_path = session.phase_dir(phase_id) / "transcript.txt"
    transcript_path.write_text("This is a test transcript for export.")
    session.phases[phase_id].transcript_file = "transcript.txt"
    session.phases[phase_id].status = "transcribed"

    # Write extracted data
    extracted_path = session.phase_dir(phase_id) / "extracted.yaml"
    with open(extracted_path, "w") as f:
        yaml.dump({"key_points": ["Point A", "Point B"], "summary": "Test"}, f)
    session.phases[phase_id].extracted_file = "extracted.yaml"
    session.phases[phase_id].status = "extracted"

    session.save()
    return session


class TestExportZip:
    """Tests for ZIP export."""

    def test_export_creates_zip(self, session_with_data, tmp_path):
        svc = ExportService()
        result = svc.export_session("export-test", format="zip", output_dir=tmp_path)

        assert isinstance(result, ExportResult)
        assert result.format == "zip"
        assert result.output_path.exists()
        assert result.output_path.suffix == ".zip"
        assert result.file_count > 0
        assert result.size_bytes > 0

    def test_zip_contains_manifest(self, session_with_data, tmp_path):
        svc = ExportService()
        result = svc.export_session("export-test", format="zip", output_dir=tmp_path)

        with zipfile.ZipFile(result.output_path) as zf:
            names = zf.namelist()
            manifest_entries = [n for n in names if n.endswith("manifest.json")]
            assert len(manifest_entries) == 1

            manifest = json.loads(zf.read(manifest_entries[0]))
            assert manifest["session_name"] == "export-test"
            assert "checksums" in manifest

    def test_zip_contains_session_and_template(self, session_with_data, tmp_path):
        svc = ExportService()
        result = svc.export_session("export-test", format="zip", output_dir=tmp_path)

        with zipfile.ZipFile(result.output_path) as zf:
            names = zf.namelist()
            assert any("session.yaml" in n for n in names)
            assert any("template.yaml" in n for n in names)

    def test_zip_contains_transcript(self, session_with_data, tmp_path):
        svc = ExportService()
        result = svc.export_session("export-test", format="zip", output_dir=tmp_path)

        with zipfile.ZipFile(result.output_path) as zf:
            names = zf.namelist()
            transcript_entries = [n for n in names if "transcript.txt" in n]
            assert len(transcript_entries) == 1

    def test_zip_contains_extracted(self, session_with_data, tmp_path):
        svc = ExportService()
        result = svc.export_session("export-test", format="zip", output_dir=tmp_path)

        with zipfile.ZipFile(result.output_path) as zf:
            names = zf.namelist()
            extracted_entries = [n for n in names if "extracted.yaml" in n]
            assert len(extracted_entries) == 1


class TestExportJson:
    """Tests for JSON export."""

    def test_export_creates_json(self, session_with_data, tmp_path):
        svc = ExportService()
        result = svc.export_session("export-test", format="json", output_dir=tmp_path)

        assert result.format == "json"
        assert result.output_path.exists()
        assert result.output_path.suffix == ".json"

    def test_json_has_session_data(self, session_with_data, tmp_path):
        svc = ExportService()
        result = svc.export_session("export-test", format="json", output_dir=tmp_path)

        with open(result.output_path) as f:
            data = json.load(f)

        assert data["session"]["name"] == "export-test"
        assert "template" in data
        assert "phases" in data

    def test_json_includes_transcript(self, session_with_data, tmp_path):
        svc = ExportService()
        result = svc.export_session("export-test", format="json", output_dir=tmp_path)

        with open(result.output_path) as f:
            data = json.load(f)

        phases = data["phases"]
        first_phase = next(iter(phases.values()))
        assert first_phase["transcript"] == "This is a test transcript for export."

    def test_json_includes_extracted(self, session_with_data, tmp_path):
        svc = ExportService()
        result = svc.export_session("export-test", format="json", output_dir=tmp_path)

        with open(result.output_path) as f:
            data = json.load(f)

        phases = data["phases"]
        first_phase = next(iter(phases.values()))
        assert first_phase["extracted"]["key_points"] == ["Point A", "Point B"]


class TestExportYaml:
    """Tests for YAML export."""

    def test_export_creates_yaml(self, session_with_data, tmp_path):
        svc = ExportService()
        result = svc.export_session("export-test", format="yaml", output_dir=tmp_path)

        assert result.format == "yaml"
        assert result.output_path.exists()
        assert result.output_path.suffix == ".yaml"

    def test_yaml_roundtrips(self, session_with_data, tmp_path):
        svc = ExportService()
        result = svc.export_session("export-test", format="yaml", output_dir=tmp_path)

        with open(result.output_path) as f:
            data = yaml.safe_load(f)

        assert data["session"]["name"] == "export-test"
        assert "template" in data
        assert "phases" in data


class TestExportInvalidFormat:
    """Tests for invalid export format."""

    def test_raises_on_unknown_format(self, session_with_data, tmp_path):
        svc = ExportService()
        with pytest.raises(ValueError, match="Unknown export format"):
            svc.export_session("export-test", format="docx", output_dir=tmp_path)

    def test_raises_on_missing_session(self, sift_home, tmp_path):
        svc = ExportService()
        with pytest.raises(Exception):
            svc.export_session("nonexistent", format="zip", output_dir=tmp_path)


class TestImportZip:
    """Tests for ZIP import (round-trip)."""

    def test_roundtrip_zip(self, session_with_data, tmp_path, sift_home):
        svc = ExportService()

        # Export
        export_result = svc.export_session("export-test", format="zip", output_dir=tmp_path)

        # Delete original
        import shutil

        shutil.rmtree(sift_home / "sessions" / "export-test")

        # Import
        import_result = svc.import_session(export_result.output_path)

        assert isinstance(import_result, ImportResult)
        assert import_result.session_name == "export-test"
        assert import_result.phase_count == 2

        # Verify data is intact
        from sift.models import Session

        session = Session.load("export-test")
        phase_id = list(session.phases.keys())[0]
        transcript = session.get_transcript(phase_id)
        assert transcript == "This is a test transcript for export."

    def test_import_zip_duplicate_fails(self, session_with_data, tmp_path):
        svc = ExportService()
        export_result = svc.export_session("export-test", format="zip", output_dir=tmp_path)

        with pytest.raises(ValueError, match="already exists"):
            svc.import_session(export_result.output_path)

    def test_import_zip_overwrite(self, session_with_data, tmp_path):
        svc = ExportService()
        export_result = svc.export_session("export-test", format="zip", output_dir=tmp_path)

        result = svc.import_session(export_result.output_path, overwrite=True)
        assert result.session_name == "export-test"


class TestImportJson:
    """Tests for JSON import (round-trip)."""

    def test_roundtrip_json(self, session_with_data, tmp_path, sift_home):
        svc = ExportService()

        # Export
        export_result = svc.export_session("export-test", format="json", output_dir=tmp_path)

        # Delete original
        import shutil

        shutil.rmtree(sift_home / "sessions" / "export-test")

        # Import
        import_result = svc.import_session(export_result.output_path)

        assert import_result.session_name == "export-test"
        assert import_result.phase_count == 2

        # Verify transcript is restored
        from sift.models import Session

        session = Session.load("export-test")
        phase_id = list(session.phases.keys())[0]
        assert session.get_transcript(phase_id) == "This is a test transcript for export."

    def test_roundtrip_json_extracted_data(self, session_with_data, tmp_path, sift_home):
        svc = ExportService()
        export_result = svc.export_session("export-test", format="json", output_dir=tmp_path)

        import shutil

        shutil.rmtree(sift_home / "sessions" / "export-test")

        svc.import_session(export_result.output_path)

        from sift.models import Session

        session = Session.load("export-test")
        phase_id = list(session.phases.keys())[0]
        extracted = session.get_extracted(phase_id)
        assert extracted["key_points"] == ["Point A", "Point B"]
        assert extracted["summary"] == "Test"


class TestImportYaml:
    """Tests for YAML import (round-trip)."""

    def test_roundtrip_yaml(self, session_with_data, tmp_path, sift_home):
        svc = ExportService()

        export_result = svc.export_session("export-test", format="yaml", output_dir=tmp_path)

        import shutil

        shutil.rmtree(sift_home / "sessions" / "export-test")

        import_result = svc.import_session(export_result.output_path)
        assert import_result.session_name == "export-test"
        assert import_result.phase_count == 2


class TestImportErrors:
    """Tests for import error handling."""

    def test_import_missing_file(self, sift_home, tmp_path):
        svc = ExportService()
        with pytest.raises(FileNotFoundError):
            svc.import_session(tmp_path / "nonexistent.zip")

    def test_import_unsupported_format(self, sift_home, tmp_path):
        bad_file = tmp_path / "data.docx"
        bad_file.write_text("not a real file")
        svc = ExportService()
        with pytest.raises(ValueError, match="Unsupported import format"):
            svc.import_session(bad_file)

    def test_import_invalid_json(self, sift_home, tmp_path):
        bad_json = tmp_path / "bad.json"
        with open(bad_json, "w") as f:
            json.dump({"foo": "bar"}, f)
        svc = ExportService()
        with pytest.raises(ValueError, match="missing 'session'"):
            svc.import_session(bad_json)


class TestExportTemplate:
    """Tests for template export."""

    def test_export_template(self, sample_template_path, tmp_path):
        svc = ExportService()
        result = svc.export_template("test-template", output_path=tmp_path / "exported.yaml")

        assert result.exists()
        with open(result) as f:
            data = yaml.safe_load(f)
        assert data["name"] == "Test Template"

    def test_export_template_missing(self, sift_home, tmp_path):
        svc = ExportService()
        with pytest.raises(Exception):
            svc.export_template("nonexistent", output_path=tmp_path / "out.yaml")


class TestImportTemplate:
    """Tests for template import."""

    def test_import_template(self, sample_template_path, sift_home, tmp_path):
        svc = ExportService()
        # Export first
        exported = svc.export_template("test-template", output_path=tmp_path / "my-template.yaml")

        # Remove the original so import doesn't conflict
        sample_template_path.unlink()

        # Import (will create slug-based name from template name)
        result = svc.import_template(exported)
        assert result.exists()
        assert "test-template" in result.name

    def test_import_template_duplicate_fails(self, sample_template_path, sift_home, tmp_path):
        svc = ExportService()
        exported = svc.export_template("test-template", output_path=tmp_path / "my-template.yaml")

        # First import succeeds
        svc.import_template(exported, overwrite=True)
        # Second without overwrite fails
        with pytest.raises(ValueError, match="already exists"):
            svc.import_template(exported)

    def test_import_template_missing_file(self, sift_home, tmp_path):
        svc = ExportService()
        with pytest.raises(FileNotFoundError):
            svc.import_template(tmp_path / "nonexistent.yaml")
