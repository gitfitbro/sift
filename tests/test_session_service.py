"""Tests for SessionService."""
import pytest
from sift.core.session_service import SessionService


class TestSessionServiceCreate:
    def test_create_session_basic(self, sample_template_path):
        svc = SessionService()
        detail = svc.create_session("test-template", name="my-test")

        assert detail.name == "my-test"
        assert detail.template_name == "Test Template"
        assert detail.status == "active"
        assert detail.total_phases == 2
        assert detail.done_phases == 0
        assert len(detail.phases) == 2
        assert detail.phases[0].id == "gather-info"
        assert detail.phases[1].id == "review"

    def test_create_session_auto_name(self, sample_template_path):
        svc = SessionService()
        detail = svc.create_session("test-template")

        assert detail.name  # auto-generated
        assert "test-template" in detail.name or "test" in detail.name.lower()

    def test_create_session_template_not_found(self):
        svc = SessionService()
        with pytest.raises(FileNotFoundError, match="not found"):
            svc.create_session("nonexistent-template")

    def test_create_session_duplicate_name(self, sample_template_path):
        svc = SessionService()
        svc.create_session("test-template", name="dup-test")

        with pytest.raises(ValueError, match="already exists"):
            svc.create_session("test-template", name="dup-test")

    def test_create_session_multi_template(self, sift_home, sample_template_path):
        """Test creating with '+' syntax (same template combined with itself)."""
        import shutil
        shutil.copy(
            sample_template_path,
            sift_home / "templates" / "other-template.yaml",
        )

        svc = SessionService()
        detail = svc.create_session("test-template+other-template", name="multi")

        assert detail.name == "multi"
        # Phases should be namespaced
        assert len(detail.phases) == 4  # 2 from each template


class TestSessionServiceList:
    def test_list_sessions_empty(self):
        svc = SessionService()
        result = svc.list_sessions()
        assert result == []

    def test_list_sessions_with_data(self, sample_template_path):
        svc = SessionService()
        svc.create_session("test-template", name="session-a")
        svc.create_session("test-template", name="session-b")

        result = svc.list_sessions()
        assert len(result) == 2
        names = {s.name for s in result}
        assert "session-a" in names
        assert "session-b" in names

    def test_list_sessions_shows_progress(self, sample_session):
        svc = SessionService()
        result = svc.list_sessions()

        assert len(result) == 1
        info = result[0]
        assert info.total_phases == 2
        assert info.done_phases == 0
        assert info.status == "active"


class TestSessionServiceStatus:
    def test_get_status(self, sample_session):
        svc = SessionService()
        detail = svc.get_session_status("test-session")

        assert detail.name == "test-session"
        assert detail.total_phases == 2
        assert detail.done_phases == 0
        assert len(detail.phases) == 2

    def test_get_status_not_found(self):
        svc = SessionService()
        with pytest.raises(FileNotFoundError):
            svc.get_session_status("nonexistent")

    def test_next_action_is_capture(self, sample_session):
        svc = SessionService()
        detail = svc.get_session_status("test-session")

        assert detail.next_action == "capture"
        assert detail.next_action_phase == "gather-info"


class TestSessionServiceExport:
    def test_export_session(self, sample_session, tmp_path):
        svc = SessionService()
        result = svc.export_session("test-session", tmp_path)

        assert result.data["session"]["name"] == "test-session"
        assert "gather-info" in result.data["phases"]
        assert "review" in result.data["phases"]
        assert result.output_path is not None
        assert result.output_path.exists()

    def test_export_session_no_output_dir(self, sample_session):
        svc = SessionService()
        result = svc.export_session("test-session")

        assert result.data["session"]["name"] == "test-session"
        assert result.output_path is None


class TestSessionServiceCompletions:
    def test_get_session_names(self, sample_session):
        svc = SessionService()
        names = svc.get_session_names()
        assert "test-session" in names

    def test_get_session_names_empty(self):
        svc = SessionService()
        names = svc.get_session_names()
        assert names == []

    def test_get_template_names(self, sample_template_path):
        svc = SessionService()
        names = svc.get_template_names()
        assert "test-template" in names

    def test_get_phase_ids(self, sample_session):
        svc = SessionService()
        ids = svc.get_phase_ids("test-session")
        assert "gather-info" in ids
        assert "review" in ids

    def test_get_phase_ids_missing_session(self):
        svc = SessionService()
        ids = svc.get_phase_ids("nonexistent")
        assert ids == []
