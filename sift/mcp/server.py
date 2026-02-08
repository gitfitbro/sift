"""MCP server exposing sift services as tools.

Runs via STDIO transport. Entry point: `sift-mcp` console script.

Usage:
    Claude Desktop: {"mcpServers": {"sift": {"command": "sift-mcp"}}}
    Claude Code:    claude mcp add sift -- sift-mcp
"""
from __future__ import annotations

import json
import logging
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP

logger = logging.getLogger("sift.mcp")

mcp = FastMCP("sift")


def _serialize(obj: object) -> object:
    """Convert dataclass/Path objects to JSON-serializable dicts."""
    if hasattr(obj, "__dataclass_fields__"):
        d = asdict(obj)
        return _clean_paths(d)
    return obj


def _clean_paths(obj: object) -> object:
    """Recursively convert Path objects to strings."""
    if isinstance(obj, Path):
        return str(obj)
    if isinstance(obj, dict):
        return {k: _clean_paths(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_clean_paths(item) for item in obj]
    return obj


# ---------------------------------------------------------------------------
# Template tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def sift_list_templates() -> dict:
    """List all available sift session templates.

    Returns template names, descriptions, and phase counts.
    """
    from sift.core.template_service import TemplateService

    svc = TemplateService()
    templates = svc.list_templates()
    return {"templates": [_serialize(t) for t in templates]}


# ---------------------------------------------------------------------------
# Session tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def sift_create_session(
    template: str,
    name: Optional[str] = None,
) -> dict:
    """Create a new sift session from a template.

    Args:
        template: Template name or "tmpl1+tmpl2" for multi-template.
        name: Optional session name. Auto-generated if omitted.
    """
    from sift.core.session_service import SessionService

    from sift.errors import SiftError

    svc = SessionService()
    try:
        detail = svc.create_session(template, name)
        return {"status": "created", "session": _serialize(detail)}
    except (SiftError, ValueError) as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
async def sift_list_sessions() -> dict:
    """List all sift sessions with their status and progress."""
    from sift.core.session_service import SessionService

    svc = SessionService()
    sessions = svc.list_sessions()
    return {"sessions": [_serialize(s) for s in sessions]}


@mcp.tool()
async def sift_session_status(session_name: str) -> dict:
    """Get detailed status for a sift session including all phases.

    Args:
        session_name: Name of the session to inspect.
    """
    from sift.core.session_service import SessionService

    from sift.errors import SiftError

    svc = SessionService()
    try:
        detail = svc.get_session_status(session_name)
        return {"status": "ok", "session": _serialize(detail)}
    except SiftError as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Capture & extraction tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def sift_capture_text(
    session_name: str,
    phase_id: str,
    text: str,
) -> dict:
    """Capture text content for a session phase.

    Args:
        session_name: Name of the session.
        phase_id: ID of the phase to capture into.
        text: The text content to capture.
    """
    from sift.core.extraction_service import ExtractionService

    from sift.errors import SiftError

    svc = ExtractionService()
    try:
        result = svc.capture_text(session_name, phase_id, text)
        return {"status": "ok", "capture": _serialize(result)}
    except SiftError as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
async def sift_extract_phase(
    session_name: str,
    phase_id: str,
) -> dict:
    """Extract structured data from a session phase using AI.

    Requires the phase to have a transcript (captured text).

    Args:
        session_name: Name of the session.
        phase_id: ID of the phase to extract from.
    """
    from sift.core.extraction_service import ExtractionService

    from sift.errors import SiftError

    svc = ExtractionService()
    try:
        result = svc.extract_phase(session_name, phase_id)
        return {"status": "ok", "extraction": _serialize(result)}
    except SiftError as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Build tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def sift_build_outputs(
    session_name: str,
    format: str = "all",
) -> dict:
    """Generate outputs from a sift session's extracted data.

    Args:
        session_name: Name of the session.
        format: Output format - "yaml", "markdown", or "all".
    """
    from sift.core.build_service import BuildService

    from sift.errors import SiftError

    svc = BuildService()
    try:
        result = svc.generate_outputs(session_name, format)
        return {
            "status": "ok",
            "output_dir": str(result.output_dir),
            "files": [
                {"label": label, "path": str(path)}
                for label, path in result.generated_files
            ],
        }
    except SiftError as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Project analysis tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def sift_analyze_project(
    project_path: str,
    include_ai_summary: bool = False,
) -> dict:
    """Analyze a software project's structure, languages, and dependencies.

    Args:
        project_path: Absolute path to the project directory.
        include_ai_summary: Whether to generate an AI architecture summary (requires API key).
    """
    from sift.analyzers.project_analyzer import ProjectAnalyzer

    analyzer = ProjectAnalyzer()
    path = Path(project_path).resolve()

    provider = None
    if include_ai_summary:
        try:
            from sift.providers import get_provider
            provider = get_provider()
        except Exception:
            logger.warning("AI provider not available for summary")

    try:
        structure = analyzer.analyze(path, provider=provider)
        result = {
            "name": structure.name,
            "root_path": str(structure.root_path),
            "languages": structure.languages,
            "total_files": structure.total_files,
            "total_lines": structure.total_lines,
            "dependencies": [_serialize(d) for d in structure.dependencies],
            "entry_points": structure.entry_points,
            "frameworks_detected": structure.frameworks_detected,
            "directory_tree": structure.directory_tree,
        }
        if structure.architecture_summary:
            result["architecture_summary"] = structure.architecture_summary
        return {"status": "ok", "project": result}
    except ValueError as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Export tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def sift_export_session(session_name: str) -> dict:
    """Export all session data (metadata, transcripts, extracted data) as JSON.

    Args:
        session_name: Name of the session to export.
    """
    from sift.core.session_service import SessionService

    from sift.errors import SiftError

    svc = SessionService()
    try:
        export = svc.export_session(session_name)
        return {"status": "ok", "data": export.data}
    except SiftError as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Run the sift MCP server via STDIO transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
