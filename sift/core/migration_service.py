"""Schema migration service - versioned data migration for sessions and templates.

Provides a registry-based approach to managing schema version upgrades.
Each migration is a function that transforms raw YAML data dicts from
one schema version to the next.
"""

from __future__ import annotations

import logging
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field

import yaml

logger = logging.getLogger("sift.core.migration")

# Type alias for migration functions: take a raw data dict, return transformed dict
MigrationFn = Callable[[dict], dict]


@dataclass
class MigrationResult:
    """Result of a single migration operation."""

    name: str
    source_version: int
    target_version: int
    migrated: bool
    dry_run: bool = False
    changes: list[str] = field(default_factory=list)


@dataclass
class MigrationSummary:
    """Summary of a batch migration run."""

    sessions: list[MigrationResult] = field(default_factory=list)
    templates: list[MigrationResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_migrated(self) -> int:
        return sum(1 for r in self.sessions + self.templates if r.migrated)

    @property
    def total_skipped(self) -> int:
        return sum(1 for r in self.sessions + self.templates if not r.migrated)


class MigrationRegistry:
    """Registry for versioned migration functions.

    Migrations are registered as functions that transform data dicts
    from one schema version to the next (e.g., v1 -> v2).
    """

    def __init__(self) -> None:
        self._session_migrations: dict[int, MigrationFn] = {}
        self._template_migrations: dict[int, MigrationFn] = {}

    def register_session_migration(self, from_version: int, fn: MigrationFn) -> None:
        """Register a session migration from from_version to from_version + 1."""
        self._session_migrations[from_version] = fn

    def register_template_migration(self, from_version: int, fn: MigrationFn) -> None:
        """Register a template migration from from_version to from_version + 1."""
        self._template_migrations[from_version] = fn

    def migrate_data(
        self,
        data: dict,
        current_version: int,
        target_version: int,
        migrations: dict[int, MigrationFn],
    ) -> tuple[dict, list[str]]:
        """Apply a chain of migrations from current_version to target_version.

        Returns the migrated data dict and a list of change descriptions.

        Raises:
            ValueError: If a required migration step is missing.
        """
        if current_version >= target_version:
            return data, []

        changes: list[str] = []
        migrated = data.copy()

        for v in range(current_version, target_version):
            fn = migrations.get(v)
            if fn is None:
                raise ValueError(
                    f"No migration registered for version {v} -> {v + 1}. "
                    f"Cannot migrate from v{current_version} to v{target_version}."
                )
            migrated = fn(migrated)
            migrated["schema_version"] = v + 1
            changes.append(f"Migrated v{v} -> v{v + 1}")
            logger.info("Applied migration v%d -> v%d", v, v + 1)

        return migrated, changes

    def migrate_session_data(self, data: dict, target_version: int) -> tuple[dict, list[str]]:
        """Migrate session data to target version."""
        current = data.get("schema_version", 1)
        return self.migrate_data(data, current, target_version, self._session_migrations)

    def migrate_template_data(self, data: dict, target_version: int) -> tuple[dict, list[str]]:
        """Migrate template data to target version."""
        current = data.get("schema_version", 1)
        return self.migrate_data(data, current, target_version, self._template_migrations)

    @property
    def session_migration_count(self) -> int:
        return len(self._session_migrations)

    @property
    def template_migration_count(self) -> int:
        return len(self._template_migrations)


class MigrationService:
    """Service for running migrations on sessions and templates."""

    def __init__(self) -> None:
        self._registry = _get_registry()

    def migrate_session(self, session_name: str, dry_run: bool = False) -> MigrationResult:
        """Migrate a single session to the current schema version.

        Args:
            session_name: Name of the session to migrate.
            dry_run: If True, preview changes without applying them.

        Raises:
            SessionNotFoundError: If the session does not exist.
        """
        from sift.errors import SessionNotFoundError
        from sift.models import SCHEMA_VERSION_SESSION, SESSIONS_DIR

        session_dir = SESSIONS_DIR / session_name
        if not session_dir.exists():
            raise SessionNotFoundError(session_name)

        session_file = session_dir / "session.yaml"
        with open(session_file) as f:
            data = yaml.safe_load(f)

        current_version = data.get("schema_version", 1)
        target_version = SCHEMA_VERSION_SESSION

        if current_version >= target_version:
            return MigrationResult(
                name=session_name,
                source_version=current_version,
                target_version=target_version,
                migrated=False,
                dry_run=dry_run,
                changes=["Already at current version"],
            )

        migrated_data, changes = self._registry.migrate_session_data(data, target_version)

        if not dry_run:
            # Backup original
            backup_path = session_file.with_suffix(".yaml.bak")
            shutil.copy2(session_file, backup_path)
            logger.info("Backed up %s to %s", session_file, backup_path)

            # Write migrated data
            with open(session_file, "w") as f:
                yaml.dump(migrated_data, f, default_flow_style=False, sort_keys=False)

        return MigrationResult(
            name=session_name,
            source_version=current_version,
            target_version=target_version,
            migrated=True,
            dry_run=dry_run,
            changes=changes,
        )

    def migrate_template(self, template_name: str, dry_run: bool = False) -> MigrationResult:
        """Migrate a single template to the current schema version."""
        from sift.models import SCHEMA_VERSION_TEMPLATE, TEMPLATES_DIR

        template_file = None
        for ext in (".yaml", ".yml"):
            candidate = TEMPLATES_DIR / f"{template_name}{ext}"
            if candidate.exists():
                template_file = candidate
                break

        if template_file is None:
            from sift.errors import TemplateNotFoundError

            raise TemplateNotFoundError(template_name, str(TEMPLATES_DIR))

        with open(template_file) as f:
            data = yaml.safe_load(f)

        current_version = data.get("schema_version", 0)
        target_version = SCHEMA_VERSION_TEMPLATE

        if current_version >= target_version:
            return MigrationResult(
                name=template_name,
                source_version=current_version,
                target_version=target_version,
                migrated=False,
                dry_run=dry_run,
                changes=["Already at current version"],
            )

        migrated_data, changes = self._registry.migrate_template_data(data, target_version)

        if not dry_run:
            backup_path = template_file.with_suffix(".yaml.bak")
            shutil.copy2(template_file, backup_path)

            with open(template_file, "w") as f:
                yaml.dump(migrated_data, f, default_flow_style=False, sort_keys=False)

        return MigrationResult(
            name=template_name,
            source_version=current_version,
            target_version=target_version,
            migrated=True,
            dry_run=dry_run,
            changes=changes,
        )

    def migrate_all_sessions(self, dry_run: bool = False) -> list[MigrationResult]:
        """Migrate all sessions."""
        from sift.models import SESSIONS_DIR

        results: list[MigrationResult] = []
        if not SESSIONS_DIR.exists():
            return results

        for session_dir in sorted(SESSIONS_DIR.iterdir()):
            if session_dir.is_dir() and (session_dir / "session.yaml").exists():
                try:
                    result = self.migrate_session(session_dir.name, dry_run=dry_run)
                    results.append(result)
                except Exception as e:
                    logger.warning("Failed to migrate session %s: %s", session_dir.name, e)
                    results.append(
                        MigrationResult(
                            name=session_dir.name,
                            source_version=0,
                            target_version=0,
                            migrated=False,
                            dry_run=dry_run,
                            changes=[f"Error: {e}"],
                        )
                    )

        return results

    def migrate_all_templates(self, dry_run: bool = False) -> list[MigrationResult]:
        """Migrate all templates."""
        from sift.models import TEMPLATES_DIR

        results: list[MigrationResult] = []
        if not TEMPLATES_DIR.exists():
            return results

        for template_file in sorted(
            list(TEMPLATES_DIR.glob("*.yaml")) + list(TEMPLATES_DIR.glob("*.yml"))
        ):
            try:
                result = self.migrate_template(template_file.stem, dry_run=dry_run)
                results.append(result)
            except Exception as e:
                logger.warning("Failed to migrate template %s: %s", template_file.stem, e)
                results.append(
                    MigrationResult(
                        name=template_file.stem,
                        source_version=0,
                        target_version=0,
                        migrated=False,
                        dry_run=dry_run,
                        changes=[f"Error: {e}"],
                    )
                )

        return results

    def migrate_all(self, dry_run: bool = False) -> MigrationSummary:
        """Migrate all sessions and templates."""
        summary = MigrationSummary()
        summary.sessions = self.migrate_all_sessions(dry_run=dry_run)
        summary.templates = self.migrate_all_templates(dry_run=dry_run)
        return summary


# ── Module-level registry singleton ──

_registry: MigrationRegistry | None = None


def _get_registry() -> MigrationRegistry:
    """Get or create the migration registry singleton."""
    global _registry
    if _registry is None:
        _registry = MigrationRegistry()
        _register_builtin_migrations(_registry)
    return _registry


def _register_builtin_migrations(registry: MigrationRegistry) -> None:
    """Register all built-in migrations.

    Currently empty since we are at schema v1. When v2 is introduced,
    add migration functions here:

        def _migrate_session_v1_to_v2(data: dict) -> dict:
            data["new_field"] = "default_value"
            return data

        registry.register_session_migration(1, _migrate_session_v1_to_v2)
    """
    pass


def get_migration_service() -> MigrationService:
    """Get a MigrationService instance."""
    return MigrationService()
