"""Session export and import service.

Supports three export formats:
  - ZIP: Portable archive with all session data and files
  - JSON: Metadata + extracted data as JSON
  - YAML: Metadata + extracted data as YAML

The ZIP archive format:
    {session-name}.sift/
    ├── manifest.json
    ├── session.yaml
    ├── template.yaml
    ├── phases/
    │   └── {phase-id}/
    │       ├── transcript.txt
    │       └── extracted.yaml
    └── outputs/
        └── *.yaml, *.md
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
import zipfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

import yaml

from sift.models import SESSIONS_DIR, TEMPLATES_DIR, Session, SessionTemplate, ensure_dirs

logger = logging.getLogger("sift.core.export")

ARCHIVE_VERSION = 1


@dataclass
class ExportResult:
    """Result of an export operation."""

    session_name: str
    format: str
    output_path: Path
    file_count: int
    size_bytes: int


@dataclass
class ImportResult:
    """Result of an import operation."""

    session_name: str
    phase_count: int
    source_path: Path
    overwritten: bool = False


class ExportService:
    """Handles session export and import operations."""

    def export_session(
        self,
        session_name: str,
        format: str = "zip",
        output_dir: Path | None = None,
        include_audio: bool = False,
    ) -> ExportResult:
        """Export a session in the specified format.

        Args:
            session_name: Name of the session to export.
            format: One of 'zip', 'json', 'yaml'.
            output_dir: Where to write the export file. Defaults to cwd.
            include_audio: Include audio files in ZIP export.

        Returns:
            ExportResult with output path and stats.

        Raises:
            SessionNotFoundError: If session doesn't exist.
            ValueError: If format is invalid.
        """
        ensure_dirs()
        session = Session.load(session_name)
        template = session.get_template()

        if output_dir is None:
            output_dir = Path.cwd()
        output_dir.mkdir(parents=True, exist_ok=True)

        if format == "zip":
            return self._export_zip(session, template, output_dir, include_audio)
        elif format == "json":
            return self._export_json(session, template, output_dir)
        elif format == "yaml":
            return self._export_yaml(session, template, output_dir)
        else:
            raise ValueError(f"Unknown export format '{format}'. Use: zip, json, yaml")

    def import_session(
        self,
        source_path: Path,
        overwrite: bool = False,
    ) -> ImportResult:
        """Import a session from a file.

        Args:
            source_path: Path to .sift.zip, .json, or .yaml file.
            overwrite: If True, overwrite existing session with same name.

        Returns:
            ImportResult with session details.

        Raises:
            FileNotFoundError: If source file doesn't exist.
            ValueError: If format is unsupported or data is invalid.
        """
        ensure_dirs()

        if not source_path.exists():
            raise FileNotFoundError(f"Import file not found: {source_path}")

        suffix = source_path.suffix.lower()
        if suffix == ".zip":
            return self._import_zip(source_path, overwrite)
        elif suffix == ".json":
            return self._import_json(source_path, overwrite)
        elif suffix in (".yaml", ".yml"):
            return self._import_yaml(source_path, overwrite)
        else:
            raise ValueError(f"Unsupported import format '{suffix}'. Use: .zip, .json, .yaml")

    def export_template(
        self,
        template_name: str,
        output_path: Path | None = None,
    ) -> Path:
        """Export a template as a standalone YAML file.

        Returns:
            Path to the exported template file.
        """
        from sift.core.template_service import TemplateService

        tmpl_svc = TemplateService()
        tmpl_path = tmpl_svc.find_template(template_name)
        template = SessionTemplate.from_file(tmpl_path)

        if output_path is None:
            output_path = Path.cwd() / f"{template_name}.yaml"

        with open(output_path, "w") as f:
            yaml.dump(template.to_dict(), f, default_flow_style=False, sort_keys=False)

        logger.info("Exported template '%s' to %s", template_name, output_path)
        return output_path

    def import_template(
        self,
        source_path: Path,
        overwrite: bool = False,
    ) -> Path:
        """Import a template from a YAML file.

        Returns:
            Path to the installed template file.
        """
        if not source_path.exists():
            raise FileNotFoundError(f"Template file not found: {source_path}")

        # Validate it's a valid template
        template = SessionTemplate.from_file(source_path)
        slug = template.name.lower().replace(" ", "-")
        dest_path = TEMPLATES_DIR / f"{slug}.yaml"

        if dest_path.exists() and not overwrite:
            raise ValueError(f"Template '{slug}' already exists. Use --overwrite to replace.")

        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_path, dest_path)
        logger.info("Imported template '%s' to %s", template.name, dest_path)
        return dest_path

    # ── ZIP Export/Import ──

    def _export_zip(
        self,
        session: Session,
        template: SessionTemplate,
        output_dir: Path,
        include_audio: bool,
    ) -> ExportResult:
        session_dir = session.dir
        archive_name = f"{session.name}.sift.zip"
        archive_path = output_dir / archive_name
        prefix = f"{session.name}.sift"

        checksums = {}
        file_count = 0

        with zipfile.ZipFile(archive_path, "w", zipfile.ZIP_DEFLATED) as zf:
            # session.yaml
            session_yaml = session_dir / "session.yaml"
            if session_yaml.exists():
                zf.write(session_yaml, f"{prefix}/session.yaml")
                checksums["session.yaml"] = self._sha256(session_yaml)
                file_count += 1

            # template.yaml
            template_yaml = session_dir / "template.yaml"
            if template_yaml.exists():
                zf.write(template_yaml, f"{prefix}/template.yaml")
                checksums["template.yaml"] = self._sha256(template_yaml)
                file_count += 1

            # phases/
            phases_dir = session_dir / "phases"
            if phases_dir.exists():
                for phase_dir in sorted(phases_dir.iterdir()):
                    if not phase_dir.is_dir():
                        continue
                    for f in sorted(phase_dir.iterdir()):
                        if not include_audio and f.suffix in (
                            ".wav",
                            ".mp3",
                            ".m4a",
                            ".ogg",
                            ".webm",
                        ):
                            continue
                        arc_path = f"{prefix}/phases/{phase_dir.name}/{f.name}"
                        zf.write(f, arc_path)
                        checksums[f"phases/{phase_dir.name}/{f.name}"] = self._sha256(f)
                        file_count += 1

            # outputs/
            outputs_dir = session_dir / "outputs"
            if outputs_dir.exists():
                for f in sorted(outputs_dir.iterdir()):
                    if f.is_file():
                        zf.write(f, f"{prefix}/outputs/{f.name}")
                        checksums[f"outputs/{f.name}"] = self._sha256(f)
                        file_count += 1

            # manifest.json
            manifest = {
                "archive_version": ARCHIVE_VERSION,
                "session_name": session.name,
                "template_name": session.template_name,
                "exported_at": datetime.now().isoformat(),
                "include_audio": include_audio,
                "file_count": file_count,
                "checksums": checksums,
            }
            zf.writestr(
                f"{prefix}/manifest.json",
                json.dumps(manifest, indent=2),
            )

        size = archive_path.stat().st_size
        logger.info(
            "Exported session '%s' as ZIP (%d files, %d bytes)", session.name, file_count, size
        )
        return ExportResult(
            session_name=session.name,
            format="zip",
            output_path=archive_path,
            file_count=file_count,
            size_bytes=size,
        )

    def _import_zip(self, source_path: Path, overwrite: bool) -> ImportResult:
        with zipfile.ZipFile(source_path, "r") as zf:
            names = zf.namelist()

            # Find the prefix (e.g. "my-session.sift/")
            prefix = None
            for n in names:
                if n.endswith("/manifest.json"):
                    prefix = n.rsplit("/manifest.json", 1)[0]
                    break

            if prefix is None:
                raise ValueError("Invalid archive: no manifest.json found")

            # Read manifest
            manifest = json.loads(zf.read(f"{prefix}/manifest.json"))
            session_name = manifest["session_name"]

            dest_dir = SESSIONS_DIR / session_name
            if dest_dir.exists():
                if not overwrite:
                    raise ValueError(
                        f"Session '{session_name}' already exists. Use --overwrite to replace."
                    )
                shutil.rmtree(dest_dir)

            # Extract all files
            for name in names:
                if name.endswith("/"):
                    continue
                # Strip prefix to get relative path
                rel = name[len(prefix) + 1 :]
                if rel == "manifest.json":
                    continue
                dest_file = dest_dir / rel
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(name) as src, open(dest_file, "wb") as dst:
                    dst.write(src.read())

            # Verify checksums
            checksums = manifest.get("checksums", {})
            for rel_path, expected_hash in checksums.items():
                file_path = dest_dir / rel_path
                if file_path.exists():
                    actual_hash = self._sha256(file_path)
                    if actual_hash != expected_hash:
                        logger.warning(
                            "Checksum mismatch for %s: expected %s, got %s",
                            rel_path,
                            expected_hash[:12],
                            actual_hash[:12],
                        )

        # Count phases
        session = Session.load(session_name)
        phase_count = len(session.phases)

        logger.info("Imported session '%s' from ZIP (%d phases)", session_name, phase_count)
        return ImportResult(
            session_name=session_name,
            phase_count=phase_count,
            source_path=source_path,
            overwritten=overwrite and dest_dir.exists(),
        )

    # ── JSON Export/Import ──

    def _export_json(
        self,
        session: Session,
        template: SessionTemplate,
        output_dir: Path,
    ) -> ExportResult:
        data = self._build_export_data(session, template)
        output_path = output_dir / f"{session.name}-export.json"

        with open(output_path, "w") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        size = output_path.stat().st_size
        logger.info("Exported session '%s' as JSON (%d bytes)", session.name, size)
        return ExportResult(
            session_name=session.name,
            format="json",
            output_path=output_path,
            file_count=1,
            size_bytes=size,
        )

    def _import_json(self, source_path: Path, overwrite: bool) -> ImportResult:
        with open(source_path) as f:
            data = json.load(f)
        return self._import_from_data(data, source_path, overwrite)

    # ── YAML Export/Import ──

    def _export_yaml(
        self,
        session: Session,
        template: SessionTemplate,
        output_dir: Path,
    ) -> ExportResult:
        data = self._build_export_data(session, template)
        output_path = output_dir / f"{session.name}-export.yaml"

        with open(output_path, "w") as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)

        size = output_path.stat().st_size
        logger.info("Exported session '%s' as YAML (%d bytes)", session.name, size)
        return ExportResult(
            session_name=session.name,
            format="yaml",
            output_path=output_path,
            file_count=1,
            size_bytes=size,
        )

    def _import_yaml(self, source_path: Path, overwrite: bool) -> ImportResult:
        with open(source_path) as f:
            data = yaml.safe_load(f)
        return self._import_from_data(data, source_path, overwrite)

    # ── Shared Helpers ──

    def _build_export_data(self, session: Session, template: SessionTemplate) -> dict:
        """Build the export dict with session metadata, template, and phase data."""
        data = {
            "archive_version": ARCHIVE_VERSION,
            "exported_at": datetime.now().isoformat(),
            "session": {
                "name": session.name,
                "template_name": session.template_name,
                "created_at": session.created_at,
                "updated_at": session.updated_at,
                "status": session.status,
            },
            "template": template.to_dict(),
            "phases": {},
        }

        for pt in template.phases:
            phase_data = {
                "name": pt.name,
                "status": session.phases[pt.id].status,
            }

            transcript = session.get_transcript(pt.id)
            if transcript:
                phase_data["transcript"] = transcript

            extracted = session.get_extracted(pt.id)
            if extracted:
                phase_data["extracted"] = extracted

            data["phases"][pt.id] = phase_data

        return data

    def _import_from_data(
        self,
        data: dict,
        source_path: Path,
        overwrite: bool,
    ) -> ImportResult:
        """Import a session from a JSON/YAML data dict."""
        if "session" not in data or "template" not in data:
            raise ValueError("Invalid import data: missing 'session' and/or 'template' keys")

        session_meta = data["session"]
        session_name = session_meta["name"]

        dest_dir = SESSIONS_DIR / session_name
        if dest_dir.exists():
            if not overwrite:
                raise ValueError(
                    f"Session '{session_name}' already exists. Use --overwrite to replace."
                )
            shutil.rmtree(dest_dir)

        # Recreate session from template
        template = SessionTemplate(
            name=data["template"].get("name", session_meta.get("template_name", "")),
            description=data["template"].get("description", ""),
            phases=[],
            outputs=[],
            metadata=data["template"].get("metadata", {}),
        )
        # Use from_dict for proper parsing of phases/outputs
        from sift.models import OutputSpec, PhaseTemplate

        template.phases = [PhaseTemplate.from_dict(p) for p in data["template"].get("phases", [])]
        template.outputs = [OutputSpec.from_dict(o) for o in data["template"].get("outputs", [])]

        session = Session.create(session_name, template)

        # Restore phase data
        phases_data = data.get("phases", {})
        for phase_id, phase_info in phases_data.items():
            if phase_id not in session.phases:
                continue

            # Restore transcript
            transcript = phase_info.get("transcript")
            if transcript:
                transcript_path = session.phase_dir(phase_id) / "transcript.txt"
                transcript_path.write_text(transcript)
                session.phases[phase_id].transcript_file = "transcript.txt"

            # Restore extracted data
            extracted = phase_info.get("extracted")
            if extracted:
                extracted_path = session.phase_dir(phase_id) / "extracted.yaml"
                with open(extracted_path, "w") as f:
                    yaml.dump(extracted, f, default_flow_style=False, sort_keys=False)
                session.phases[phase_id].extracted_file = "extracted.yaml"

            # Restore status
            status = phase_info.get("status", "pending")
            session.phases[phase_id].status = status

        # Restore session-level metadata
        session.status = session_meta.get("status", "active")
        session.save()

        logger.info(
            "Imported session '%s' from %s (%d phases)",
            session_name,
            source_path.suffix,
            len(session.phases),
        )
        return ImportResult(
            session_name=session_name,
            phase_count=len(session.phases),
            source_path=source_path,
            overwritten=overwrite,
        )

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()
