"""Analysis-session integration service.

Bridges project analysis (sift analyze) with the session workflow by:
- Serializing ProjectStructure into phase transcripts and stored context
- Creating sessions pre-populated with analysis data
- Injecting project context into all extraction operations
"""

from __future__ import annotations

import logging
from pathlib import Path

import yaml

from sift.analyzers.models import ProjectStructure
from sift.analyzers.project_analyzer import ProjectAnalyzer
from sift.core import AnalysisSessionResult
from sift.core.extraction_service import ExtractionService
from sift.core.session_service import SessionService
from sift.core.template_service import TemplateService
from sift.models import Session, ensure_dirs
from sift.providers.base import AIProvider

logger = logging.getLogger("sift.core.analysis")

# Keywords used to match phases for auto-population
_ARCHITECTURE_KEYWORDS = {"architecture", "overview", "structure", "design", "context"}
_DEPENDENCY_KEYWORDS = {"dependency", "dependencies", "packages", "audit"}
_QUALITY_KEYWORDS = {"quality", "complexity", "hotspot", "review"}
_CONTEXT_KEYWORDS = {"current", "state", "background", "describe", "inventory", "infrastructure"}
_WORKFLOW_KEYWORDS = {"workflow", "process", "pipeline", "flow", "steps", "deployment"}


def serialize_analysis_text(structure: ProjectStructure) -> str:
    """Convert ProjectStructure to human-readable text for use as a phase transcript."""
    parts = [
        f"# Project Analysis: {structure.name}",
        "",
        "## Overview",
        f"- Total files: {structure.total_files}",
        f"- Total lines of code: {structure.total_lines:,}",
    ]

    if structure.languages:
        lang_lines = [
            f"  - {lang}: {count} files"
            for lang, count in sorted(structure.languages.items(), key=lambda x: -x[1])
        ]
        parts.append("- Languages:\n" + "\n".join(lang_lines))

    if structure.frameworks_detected:
        parts.append(f"- Frameworks detected: {', '.join(structure.frameworks_detected)}")

    if structure.entry_points:
        parts.append(f"- Entry points: {', '.join(structure.entry_points[:10])}")

    if structure.dependencies:
        dep_section = ["", "## Dependencies"]
        for dep in structure.dependencies[:30]:
            version_str = f" ({dep.version})" if dep.version else ""
            dep_section.append(f"- {dep.name}{version_str} [from {dep.source}]")
        if len(structure.dependencies) > 30:
            dep_section.append(f"  ... and {len(structure.dependencies) - 30} more")
        parts.extend(dep_section)

    if structure.directory_tree:
        parts.extend(["", "## Directory Structure", "```", structure.directory_tree, "```"])

    if structure.architecture_summary:
        parts.extend(["", "## Architecture Summary", structure.architecture_summary])

    # Top complexity files
    top_complex = sorted(
        [f for f in structure.file_analyses if f.complexity_score > 0],
        key=lambda f: f.complexity_score,
        reverse=True,
    )[:10]
    if top_complex:
        parts.extend(["", "## Complexity Hotspots"])
        for fa in top_complex:
            try:
                rel = str(fa.path.relative_to(structure.root_path))
            except ValueError:
                rel = str(fa.path)
            parts.append(
                f"- {rel}: {fa.line_count} lines, {len(fa.functions)} functions, "
                f"complexity={fa.complexity_score:.1f}"
            )

    return "\n".join(parts)


def serialize_analysis_context(structure: ProjectStructure) -> dict:
    """Convert ProjectStructure to a structured dict for storage and context injection."""
    return {
        "project_name": structure.name,
        "root_path": str(structure.root_path),
        "languages": structure.languages,
        "total_files": structure.total_files,
        "total_lines": structure.total_lines,
        "frameworks": structure.frameworks_detected,
        "entry_points": structure.entry_points[:10],
        "dependencies": [
            {"name": d.name, "version": d.version, "source": d.source}
            for d in structure.dependencies[:30]
        ],
        "directory_tree": structure.directory_tree,
        "architecture_summary": structure.architecture_summary or "",
    }


class AnalysisService:
    """Orchestrates analysis-to-session integration."""

    def __init__(self):
        self._analyzer = ProjectAnalyzer()
        self._session_svc = SessionService()
        self._extraction_svc = ExtractionService()
        self._template_svc = TemplateService()

    def analyze_and_create_session(
        self,
        project_path: Path,
        provider: AIProvider | None = None,
        session_name: str | None = None,
    ) -> AnalysisSessionResult:
        """One-shot: analyze project, generate template, create session, populate phases.

        Args:
            project_path: Path to the project directory.
            provider: Optional AI provider for enhanced analysis.
            session_name: Optional session name (auto-generated if omitted).

        Returns:
            AnalysisSessionResult with created session details.
        """
        ensure_dirs()
        project_path = project_path.resolve()

        # Analyze
        structure = self._analyzer.analyze(project_path, provider=provider)
        return self.create_session_from_structure(
            structure, provider=provider, session_name=session_name
        )

    def create_session_from_structure(
        self,
        structure: ProjectStructure,
        provider: AIProvider | None = None,
        session_name: str | None = None,
    ) -> AnalysisSessionResult:
        """Create a session from a pre-computed ProjectStructure (avoids re-analysis).

        Args:
            structure: Already-computed project analysis.
            provider: Optional AI provider for template recommendation.
            session_name: Optional session name (auto-generated if omitted).

        Returns:
            AnalysisSessionResult with created session details.
        """
        ensure_dirs()

        # Generate and save template
        rec = self._analyzer.recommend_template(structure, provider=provider)
        template_data = {
            "name": rec.template_name,
            "description": rec.description,
            "phases": rec.phases,
            "outputs": [
                {"type": "yaml", "template": "session-config"},
                {"type": "markdown", "template": "session-summary"},
            ],
        }
        tmpl_path = self._template_svc.create_template(template_data)

        # Create session from generated template
        detail = self._session_svc.create_session(tmpl_path.stem, name=session_name)

        # Populate matching phases (_populate_matching_phases includes fallback to first phase)
        populated_phases = self._populate_matching_phases(detail.name, structure)

        # Store analysis context alongside session
        analysis_path = self._store_analysis(detail.name, serialize_analysis_context(structure))

        # Refresh detail to reflect populated phase
        detail = self._session_svc.get_session_status(detail.name)

        return AnalysisSessionResult(
            session_detail=detail,
            analysis_path=analysis_path,
            populated_phases=populated_phases,
            template_name=rec.template_name,
        )

    def create_session_with_analysis(
        self,
        template_arg: str,
        project_path: Path,
        provider: AIProvider | None = None,
        session_name: str | None = None,
    ) -> AnalysisSessionResult:
        """Two-step: create session from template, then populate with analysis data.

        Args:
            template_arg: Template name or path.
            project_path: Path to the project directory.
            provider: Optional AI provider for enhanced analysis.
            session_name: Optional session name.

        Returns:
            AnalysisSessionResult with created session details.
        """
        ensure_dirs()
        project_path = project_path.resolve()

        # Create session normally
        detail = self._session_svc.create_session(template_arg, name=session_name)

        # Analyze project
        structure = self._analyzer.analyze(project_path, provider=provider)

        # Auto-populate matching phases
        populated_phases = self._populate_matching_phases(detail.name, structure)

        # Store analysis context
        analysis_path = self._store_analysis(detail.name, serialize_analysis_context(structure))

        detail = self._session_svc.get_session_status(detail.name)

        return AnalysisSessionResult(
            session_detail=detail,
            analysis_path=analysis_path,
            populated_phases=populated_phases,
            template_name=detail.template_name,
        )

    def capture_analysis(
        self,
        session_name: str,
        phase_id: str,
        project_path: Path,
        provider: AIProvider | None = None,
        append: bool = False,
    ) -> None:
        """Capture source: run analysis and write output as phase transcript.

        Args:
            session_name: Name of the session.
            phase_id: Phase ID to populate.
            project_path: Path to the project directory.
            provider: Optional AI provider.
            append: Whether to append to existing transcript.
        """
        project_path = project_path.resolve()
        structure = self._analyzer.analyze(project_path, provider=provider)
        analysis_text = serialize_analysis_text(structure)

        self._extraction_svc.capture_text(session_name, phase_id, analysis_text, append=append)

        # Store analysis context if not already present
        s = Session.load(session_name)
        analysis_path = s.dir / "analysis.yaml"
        if not analysis_path.exists():
            self._store_analysis(session_name, serialize_analysis_context(structure))

    def get_analysis_context(self, session_name: str) -> dict | None:
        """Load stored project analysis context for a session.

        Returns:
            The analysis context dict, or None if not stored.
        """
        s = Session.load(session_name)
        analysis_path = s.dir / "analysis.yaml"
        if analysis_path.exists():
            with open(analysis_path) as f:
                return yaml.safe_load(f)
        return None

    def _store_analysis(self, session_name: str, context: dict) -> Path:
        """Persist analysis context as analysis.yaml in the session directory."""
        s = Session.load(session_name)
        analysis_path = s.dir / "analysis.yaml"
        with open(analysis_path, "w") as f:
            yaml.dump(context, f, default_flow_style=False, sort_keys=False)
        logger.info("Analysis context stored at %s", analysis_path)
        return analysis_path

    def _populate_matching_phases(
        self, session_name: str, structure: ProjectStructure
    ) -> list[str]:
        """Auto-populate phases whose IDs/names match analysis categories.

        Uses keyword heuristics to identify architecture, dependency, and
        quality-related phases and populates them with relevant analysis data.
        """
        s = Session.load(session_name)
        tmpl = s.get_template()
        analysis_text = serialize_analysis_text(structure)
        populated = []

        for pt in tmpl.phases:
            ps = s.phases.get(pt.id)
            if not ps or ps.status != "pending":
                continue

            phase_words = set(pt.id.lower().replace("-", " ").replace("_", " ").split())
            phase_words |= set(pt.name.lower().replace("-", " ").replace("_", " ").split())

            if phase_words & _ARCHITECTURE_KEYWORDS:
                self._extraction_svc.capture_text(session_name, pt.id, analysis_text)
                populated.append(pt.id)
            elif phase_words & _DEPENDENCY_KEYWORDS and structure.dependencies:
                dep_text = self._build_dependency_text(structure)
                self._extraction_svc.capture_text(session_name, pt.id, dep_text)
                populated.append(pt.id)
            elif phase_words & _QUALITY_KEYWORDS and structure.file_analyses:
                quality_text = self._build_quality_text(structure)
                self._extraction_svc.capture_text(session_name, pt.id, quality_text)
                populated.append(pt.id)
            elif phase_words & (_CONTEXT_KEYWORDS | _WORKFLOW_KEYWORDS):
                self._extraction_svc.capture_text(session_name, pt.id, analysis_text)
                populated.append(pt.id)

        # Fallback: if no keywords matched, populate the first pending phase
        if not populated:
            for pt in tmpl.phases:
                ps = s.phases.get(pt.id)
                if ps and ps.status == "pending":
                    self._extraction_svc.capture_text(session_name, pt.id, analysis_text)
                    populated.append(pt.id)
                    break

        return populated

    def _build_dependency_text(self, structure: ProjectStructure) -> str:
        """Build dependency-focused transcript text."""
        parts = [
            f"# Dependency Audit: {structure.name}",
            "",
            f"Total dependencies: {len(structure.dependencies)}",
            f"Frameworks detected: {', '.join(structure.frameworks_detected) or 'None'}",
            "",
        ]
        for dep in structure.dependencies:
            version_str = f" ({dep.version})" if dep.version else ""
            parts.append(f"- {dep.name}{version_str} [from {dep.source}]")
        return "\n".join(parts)

    def _build_quality_text(self, structure: ProjectStructure) -> str:
        """Build code quality-focused transcript text."""
        parts = [
            f"# Code Quality Review: {structure.name}",
            "",
            f"Total files analyzed: {structure.total_files}",
            f"Total lines: {structure.total_lines:,}",
            "",
            "## Complexity Hotspots",
        ]
        top = sorted(
            [f for f in structure.file_analyses if f.complexity_score > 0],
            key=lambda f: f.complexity_score,
            reverse=True,
        )[:15]
        for fa in top:
            try:
                rel = str(fa.path.relative_to(structure.root_path))
            except ValueError:
                rel = str(fa.path)
            parts.append(
                f"- {rel}: {fa.line_count} lines, "
                f"{len(fa.functions)} functions, {len(fa.classes)} classes, "
                f"complexity={fa.complexity_score:.1f}, doc_coverage={fa.doc_coverage:.0%}"
            )
        return "\n".join(parts)
