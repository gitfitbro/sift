"""Shared fixtures for sift tests."""
import os
import shutil
import yaml
import pytest
from pathlib import Path
from unittest.mock import MagicMock


@pytest.fixture(autouse=True)
def sift_home(tmp_path, monkeypatch):
    """Set SIFT_HOME to a temporary directory for every test.

    This ensures tests never touch real data. The temp directory gets:
    - templates/ with a sample template
    - sessions/ (empty)
    """
    home = tmp_path / "sift-data"
    home.mkdir()
    (home / "templates").mkdir()
    (home / "sessions").mkdir()

    monkeypatch.setenv("SIFT_HOME", str(home))

    # Force re-evaluation of paths in sift.models
    import sift.models as models
    monkeypatch.setattr(models, "BASE_DIR", home)
    monkeypatch.setattr(models, "TEMPLATES_DIR", home / "templates")
    monkeypatch.setattr(models, "SESSIONS_DIR", home / "sessions")

    # Also patch the local references imported into service modules
    import sift.core.session_service as session_svc
    import sift.core.template_service as template_svc
    monkeypatch.setattr(session_svc, "SESSIONS_DIR", home / "sessions")
    monkeypatch.setattr(template_svc, "TEMPLATES_DIR", home / "templates")

    return home


@pytest.fixture
def sample_template_path(sift_home):
    """Create a sample template file and return its path."""
    template_data = {
        "name": "Test Template",
        "description": "A template for testing",
        "phases": [
            {
                "id": "gather-info",
                "name": "Gather Information",
                "prompt": "Collect relevant information about the topic.",
                "capture": [{"type": "text", "required": True}],
                "extract": [
                    {
                        "id": "key_points",
                        "type": "list",
                        "prompt": "List the key points discussed.",
                    },
                    {
                        "id": "summary",
                        "type": "text",
                        "prompt": "Summarize the main topic.",
                    },
                ],
            },
            {
                "id": "review",
                "name": "Review & Validate",
                "prompt": "Review the gathered information for accuracy.",
                "capture": [{"type": "text", "required": False}],
                "extract": [
                    {
                        "id": "issues_found",
                        "type": "list",
                        "prompt": "List any issues or gaps found.",
                    },
                    {
                        "id": "approved",
                        "type": "boolean",
                        "prompt": "Is the information approved?",
                    },
                ],
                "depends_on": "gather-info",
            },
        ],
        "outputs": [
            {"type": "yaml", "template": "session-config"},
            {"type": "markdown", "template": "session-summary"},
        ],
    }

    path = sift_home / "templates" / "test-template.yaml"
    with open(path, "w") as f:
        yaml.dump(template_data, f, default_flow_style=False, sort_keys=False)

    return path


@pytest.fixture
def sample_template(sample_template_path):
    """Load and return a sample SessionTemplate."""
    from sift.models import SessionTemplate
    return SessionTemplate.from_file(sample_template_path)


@pytest.fixture
def sample_session(sample_template):
    """Create and return a sample Session."""
    from sift.models import Session
    return Session.create("test-session", sample_template)


@pytest.fixture
def mock_provider():
    """Create a mock AI provider."""
    provider = MagicMock()
    provider.name = "mock"
    provider.model = "mock-model-1"
    provider.is_available.return_value = True
    provider.chat.return_value = "key_points:\n  - Point 1\n  - Point 2\nsummary: Test summary"
    provider.transcribe.return_value = "This is a mock transcription."
    return provider
