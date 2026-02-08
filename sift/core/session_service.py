"""Session management service - business logic for session operations."""

from __future__ import annotations

import logging
from datetime import datetime
from pathlib import Path

import yaml

from sift.core import (
    ExportData,
    PhaseDetail,
    SessionDetail,
    SessionInfo,
)
from sift.core.template_service import TemplateService
from sift.models import (
    SESSIONS_DIR,
    Session,
    SessionTemplate,
    ensure_dirs,
    merge_templates,
)

logger = logging.getLogger("sift.core.session")


class SessionService:
    """Manages session lifecycle operations."""

    def __init__(self):
        self._template_svc = TemplateService()

    def create_session(self, template_arg: str, name: str | None = None) -> SessionDetail:
        """Create a new session from a template argument.

        The template_arg supports '+' syntax for combining templates.

        Args:
            template_arg: Template name or "tmpl1+tmpl2" for multi-template.
            name: Optional session name. Auto-generated if omitted.

        Returns:
            SessionDetail with the created session info.

        Raises:
            FileNotFoundError: If template not found.
            ValueError: If session name already exists.
        """
        ensure_dirs()

        template_specs = self._parse_template_arg(template_arg)

        if len(template_specs) == 1:
            _stem, path = template_specs[0]
            tmpl = SessionTemplate.from_file(path)
        else:
            templates = []
            stems = []
            for stem, path in template_specs:
                templates.append(SessionTemplate.from_file(path))
                stems.append(stem)
            tmpl = merge_templates(templates, stems)

        if not name:
            date_str = datetime.now().strftime("%Y-%m-%d")
            if len(template_specs) == 1:
                slug = tmpl.name.lower().replace(" ", "-")[:30]
                name = f"{date_str}_{slug}"
            else:
                slug = template_specs[0][0][:20] + f"+{len(template_specs) - 1}more"
                name = f"{date_str}_{slug}"

        if (SESSIONS_DIR / name).exists():
            raise ValueError(f"Session '{name}' already exists")

        session = Session.create(name, tmpl)
        logger.info("Session '%s' created from template '%s'", name, tmpl.name)

        return self._build_session_detail(session, tmpl)

    def list_sessions(self) -> list[SessionInfo]:
        """List all sessions sorted by most recently updated."""
        ensure_dirs()

        session_dirs = (
            [d for d in SESSIONS_DIR.iterdir() if d.is_dir() and (d / "session.yaml").exists()]
            if SESSIONS_DIR.exists()
            else []
        )

        results = []
        for sd in sorted(session_dirs, key=lambda d: d.stat().st_mtime, reverse=True):
            try:
                s = Session.load(sd.name)
                total = len(s.phases)
                done = sum(1 for p in s.phases.values() if p.status in ("extracted", "complete"))
                in_prog = sum(
                    1 for p in s.phases.values() if p.status in ("captured", "transcribed")
                )
                results.append(
                    SessionInfo(
                        name=s.name,
                        template_name=s.template_name,
                        status=s.status,
                        total_phases=total,
                        done_phases=done,
                        in_progress_phases=in_prog,
                        updated_at=s.updated_at,
                    )
                )
            except Exception as e:
                logger.warning("Failed to load session %s: %s", sd.name, e)
                results.append(
                    SessionInfo(
                        name=sd.name,
                        template_name="?",
                        status="error",
                        total_phases=0,
                        done_phases=0,
                        in_progress_phases=0,
                        updated_at="",
                    )
                )

        return results

    def get_session_status(self, session_name: str) -> SessionDetail:
        """Get detailed status for a session.

        Raises:
            FileNotFoundError: If session not found.
        """
        ensure_dirs()
        s = Session.load(session_name)
        tmpl = s.get_template()
        return self._build_session_detail(s, tmpl)

    def export_session(self, session_name: str, output_dir: Path = None) -> ExportData:
        """Export all session data as a dict.

        Raises:
            FileNotFoundError: If session not found.
        """
        ensure_dirs()
        s = Session.load(session_name)
        tmpl = s.get_template()

        export = {
            "session": {
                "name": s.name,
                "template": s.template_name,
                "created_at": s.created_at,
                "status": s.status,
            },
            "phases": {},
        }

        for pt in tmpl.phases:
            phase_data = {"name": pt.name, "status": s.phases[pt.id].status}

            transcript = s.get_transcript(pt.id)
            if transcript:
                phase_data["transcript"] = transcript

            extracted = s.get_extracted(pt.id)
            if extracted:
                phase_data["extracted"] = extracted

            export["phases"][pt.id] = phase_data

        out_path = None
        if output_dir:
            out_path = output_dir / f"{session_name}-export.yaml"
            with open(out_path, "w") as f:
                yaml.dump(
                    export,
                    f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
            logger.info("Exported session '%s' to %s", session_name, out_path)

        return ExportData(data=export, output_path=out_path)

    def get_session_names(self) -> list[str]:
        """Get all session names (for shell completion)."""
        ensure_dirs()
        if not SESSIONS_DIR.exists():
            return []
        return sorted(
            d.name for d in SESSIONS_DIR.iterdir() if d.is_dir() and (d / "session.yaml").exists()
        )

    def get_phase_ids(self, session_name: str) -> list[str]:
        """Get all phase IDs for a session (for shell completion)."""
        try:
            s = Session.load(session_name)
            return list(s.phases.keys())
        except Exception:
            return []

    def get_template_names(self) -> list[str]:
        """Delegate to TemplateService for template names."""
        return self._template_svc.get_template_names()

    def _parse_template_arg(self, template_arg: str) -> list[tuple[str, Path]]:
        """Parse template argument that may contain '+' for multi-template."""
        names = [t.strip() for t in template_arg.split("+")]
        results = []
        for name in names:
            path = self._template_svc.find_template(name)
            results.append((name, path))
        return results

    def _build_session_detail(self, s: Session, tmpl: SessionTemplate) -> SessionDetail:
        """Build a SessionDetail from a Session and its template."""
        phases = []
        for pt in tmpl.phases:
            ps = s.phases.get(pt.id)
            phases.append(
                PhaseDetail(
                    id=pt.id,
                    name=pt.name,
                    status=ps.status if ps else "pending",
                    has_audio=bool(ps and ps.audio_file),
                    has_transcript=bool(ps and ps.transcript_file),
                    has_extracted=bool(ps and ps.extracted_file),
                    captured_at=ps.captured_at if ps else None,
                    source_document=ps.source_document if ps else None,
                    source_pages=ps.source_pages if ps else None,
                )
            )

        total = len(s.phases)
        done = sum(1 for p in s.phases.values() if p.status in ("extracted", "complete"))

        # Determine next action
        next_action = None
        next_action_phase = None
        for pt in tmpl.phases:
            ps = s.phases.get(pt.id)
            if ps and ps.status == "transcribed":
                next_action = "extract"
                next_action_phase = pt.id
                break
        if not next_action:
            for pt in tmpl.phases:
                ps = s.phases.get(pt.id)
                if ps and ps.status == "captured":
                    next_action = "transcribe"
                    next_action_phase = pt.id
                    break
        if not next_action:
            for pt in tmpl.phases:
                ps = s.phases.get(pt.id)
                if ps and ps.status == "pending":
                    next_action = "capture"
                    next_action_phase = pt.id
                    break
        if not next_action and done == total:
            next_action = "build"

        return SessionDetail(
            name=s.name,
            template_name=s.template_name,
            status=s.status,
            created_at=s.created_at,
            updated_at=s.updated_at,
            total_phases=total,
            done_phases=done,
            phases=phases,
            next_action=next_action,
            next_action_phase=next_action_phase,
        )
