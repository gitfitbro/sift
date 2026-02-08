"""Tests for schema versioning in session and template YAML files."""

import pytest
import yaml

from sift.errors import SchemaVersionError, SessionNotFoundError
from sift.models import (
    SCHEMA_VERSION_SESSION,
    SCHEMA_VERSION_TEMPLATE,
    Session,
    SessionTemplate,
)


class TestSessionSchemaVersion:
    def test_save_includes_schema_version(self, sample_session):
        yaml_path = sample_session.dir / "session.yaml"
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        assert "schema_version" in data
        assert data["schema_version"] == SCHEMA_VERSION_SESSION

    def test_load_old_session_without_version(self, sample_session):
        """Old sessions (no schema_version field) load successfully."""
        yaml_path = sample_session.dir / "session.yaml"
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        del data["schema_version"]
        with open(yaml_path, "w") as f:
            yaml.dump(data, f)

        s = Session.load(sample_session.name)
        assert s.name == sample_session.name

    def test_load_future_version_raises(self, sample_session):
        yaml_path = sample_session.dir / "session.yaml"
        with open(yaml_path) as f:
            data = yaml.safe_load(f)
        data["schema_version"] = 999
        with open(yaml_path, "w") as f:
            yaml.dump(data, f)

        with pytest.raises(SchemaVersionError, match="v999"):
            Session.load(sample_session.name)

    def test_load_nonexistent_raises_session_not_found(self):
        with pytest.raises(SessionNotFoundError):
            Session.load("nonexistent-session-xyz")


class TestTemplateSchemaVersion:
    def test_to_dict_includes_version(self, sample_template):
        d = sample_template.to_dict()
        assert "schema_version" in d
        assert d["schema_version"] == SCHEMA_VERSION_TEMPLATE

    def test_load_old_template_without_version(self, sample_template_path):
        """Old templates (no schema_version) load successfully."""
        with open(sample_template_path) as f:
            data = yaml.safe_load(f)
        data.pop("schema_version", None)
        with open(sample_template_path, "w") as f:
            yaml.dump(data, f)

        t = SessionTemplate.from_file(sample_template_path)
        assert t.name == "Test Template"

    def test_future_template_version_raises(self, sample_template_path):
        with open(sample_template_path) as f:
            data = yaml.safe_load(f)
        data["schema_version"] = 999
        with open(sample_template_path, "w") as f:
            yaml.dump(data, f)

        with pytest.raises(SchemaVersionError, match="v999"):
            SessionTemplate.from_file(sample_template_path)

    def test_current_version_loads_fine(self, sample_template_path):
        with open(sample_template_path) as f:
            data = yaml.safe_load(f)
        data["schema_version"] = SCHEMA_VERSION_TEMPLATE
        with open(sample_template_path, "w") as f:
            yaml.dump(data, f)

        t = SessionTemplate.from_file(sample_template_path)
        assert t.name == "Test Template"
