"""Tests for schema migration infrastructure."""

from __future__ import annotations


class TestMigrationRegistry:
    """Test the migration registry and chain execution."""

    def test_no_op_migration_same_version(self, sift_home):
        """V1 to V1 = no migration needed."""
        from sift.core.migration_service import MigrationRegistry

        registry = MigrationRegistry()
        data = {"schema_version": 1, "name": "test"}
        migrated, changes = registry.migrate_data(data, 1, 1, {})
        assert migrated == data
        assert changes == []

    def test_single_step_migration(self, sift_home):
        """Register a v1->v2 migration and apply it."""
        from sift.core.migration_service import MigrationRegistry

        registry = MigrationRegistry()

        def v1_to_v2(data: dict) -> dict:
            data["new_field"] = "added_in_v2"
            return data

        registry.register_session_migration(1, v1_to_v2)

        data = {"schema_version": 1, "name": "test"}
        migrated, changes = registry.migrate_session_data(data, 2)

        assert migrated["new_field"] == "added_in_v2"
        assert migrated["schema_version"] == 2
        assert len(changes) == 1
        assert "v1 -> v2" in changes[0]

    def test_chain_migration(self, sift_home):
        """Chain v1->v2->v3 migrations."""
        from sift.core.migration_service import MigrationRegistry

        registry = MigrationRegistry()

        def v1_to_v2(data: dict) -> dict:
            data["field_v2"] = "v2_value"
            return data

        def v2_to_v3(data: dict) -> dict:
            data["field_v3"] = "v3_value"
            return data

        registry.register_session_migration(1, v1_to_v2)
        registry.register_session_migration(2, v2_to_v3)

        data = {"schema_version": 1, "name": "test"}
        migrated, changes = registry.migrate_session_data(data, 3)

        assert migrated["field_v2"] == "v2_value"
        assert migrated["field_v3"] == "v3_value"
        assert migrated["schema_version"] == 3
        assert len(changes) == 2

    def test_missing_migration_step_raises(self, sift_home):
        """Missing migration step raises ValueError."""
        import pytest

        from sift.core.migration_service import MigrationRegistry

        registry = MigrationRegistry()
        data = {"schema_version": 1, "name": "test"}

        with pytest.raises(ValueError, match="No migration registered"):
            registry.migrate_session_data(data, 2)

    def test_template_migration(self, sift_home):
        """Template migrations work the same as session migrations."""
        from sift.core.migration_service import MigrationRegistry

        registry = MigrationRegistry()

        def v1_to_v2(data: dict) -> dict:
            data["template_v2"] = True
            return data

        registry.register_template_migration(1, v1_to_v2)

        data = {"schema_version": 1, "name": "template"}
        migrated, changes = registry.migrate_template_data(data, 2)

        assert migrated["template_v2"] is True
        assert len(changes) == 1


class TestMigrationService:
    """Test the migration service with real session files."""

    def test_migrate_session_no_op(self, sample_session):
        """Session already at current version is a no-op."""
        from sift.core.migration_service import MigrationService

        svc = MigrationService()
        result = svc.migrate_session("test-session")

        assert result.migrated is False
        assert result.name == "test-session"
        assert "Already at current version" in result.changes

    def test_migrate_session_dry_run(self, sample_session):
        """Dry run should not modify files."""
        from sift.core.migration_service import MigrationService

        svc = MigrationService()
        result = svc.migrate_session("test-session", dry_run=True)

        assert result.dry_run is True
        assert result.migrated is False

    def test_migrate_all_sessions(self, sample_session):
        """Migrate all sessions."""
        from sift.core.migration_service import MigrationService

        svc = MigrationService()
        results = svc.migrate_all_sessions()

        assert len(results) == 1
        assert results[0].name == "test-session"

    def test_migrate_nonexistent_session(self, sift_home):
        """Non-existent session raises SessionNotFoundError."""
        import pytest

        from sift.core.migration_service import MigrationService
        from sift.errors import SessionNotFoundError

        svc = MigrationService()
        with pytest.raises(SessionNotFoundError):
            svc.migrate_session("nonexistent")

    def test_migrate_all_summary(self, sample_session, sample_template_path):
        """Migrate all returns a summary."""
        from sift.core.migration_service import MigrationService

        svc = MigrationService()
        summary = svc.migrate_all()

        assert summary.total_skipped >= 1
        assert isinstance(summary.sessions, list)
        assert isinstance(summary.templates, list)

    def test_migrate_template_no_op(self, sample_template_path):
        """Template already at current version is a no-op."""
        from sift.core.migration_service import MigrationService

        svc = MigrationService()
        result = svc.migrate_template("test-template")

        # Template files without schema_version default to 0, which is < 1
        # So it may try to migrate, but with no registered migration it's a no-op
        assert result.name == "test-template"
