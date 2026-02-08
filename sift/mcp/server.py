"""MCP server exposing sift services as tools.

Runs via STDIO transport. Entry point: `sift-mcp` console script.

Usage:
    Claude Desktop: {"mcpServers": {"sift": {"command": "sift-mcp"}}}
    Claude Code:    claude mcp add sift -- sift-mcp
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from pathlib import Path

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
    name: str | None = None,
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
                {"label": label, "path": str(path)} for label, path in result.generated_files
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
# Template management tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def sift_create_template(
    name: str,
    description: str,
    phases: list[dict],
    outputs: list[dict] | None = None,
    metadata: dict | None = None,
) -> dict:
    """Create a new sift session template.

    Args:
        name: Template name (e.g., "discovery-call").
        description: What this template is for.
        phases: List of phase definitions, each with id, name, prompt, capture, extract.
        outputs: Optional output specs. Defaults to YAML + Markdown.
        metadata: Optional metadata (author, version, tags, license).
    """
    from sift.core.template_service import TemplateService

    svc = TemplateService()
    try:
        template_data = {
            "name": name,
            "description": description,
            "phases": phases,
            "outputs": outputs
            or [
                {"type": "yaml", "template": "session-config"},
                {"type": "markdown", "template": "session-summary"},
            ],
            "metadata": metadata or {},
        }
        path = svc.create_template(template_data)
        return {"status": "created", "path": str(path)}
    except (ValueError, Exception) as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
async def sift_search_templates(query: str) -> dict:
    """Search templates by name, description, or tags.

    Args:
        query: Search string to match against templates.
    """
    from sift.core.template_service import TemplateService

    svc = TemplateService()
    results = svc.search_templates(query)
    return {"templates": [_serialize(t) for t in results]}


# ---------------------------------------------------------------------------
# Configuration & diagnostics tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def sift_doctor() -> dict:
    """Run diagnostic checks on the sift environment.

    Returns structured results for Python version, data directories,
    templates, providers, and optional dependencies.
    """
    import sys

    checks = []

    # Python version
    py_ver = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    py_ok = sys.version_info >= (3, 10)
    checks.append({"check": "python_version", "ok": py_ok, "detail": py_ver})

    # Data directories
    from sift.models import SESSIONS_DIR, TEMPLATES_DIR

    checks.append(
        {"check": "templates_dir", "ok": TEMPLATES_DIR.exists(), "detail": str(TEMPLATES_DIR)}
    )
    checks.append(
        {"check": "sessions_dir", "ok": SESSIONS_DIR.exists(), "detail": str(SESSIONS_DIR)}
    )

    # Template count
    tmpl_count = 0
    if TEMPLATES_DIR.exists():
        tmpl_count = len(list(TEMPLATES_DIR.glob("*.yaml"))) + len(
            list(TEMPLATES_DIR.glob("*.yml"))
        )
    checks.append(
        {"check": "templates_installed", "ok": tmpl_count > 0, "detail": f"{tmpl_count} templates"}
    )

    # Provider keys
    from sift.core.secrets import list_stored_providers

    key_status = list_stored_providers()
    for provider, status in key_status.items():
        has_key = status in ("env", "keyring", "file", "no key needed")
        checks.append({"check": f"provider_{provider}", "ok": has_key, "detail": status})

    all_ok = all(c["ok"] for c in checks if not str(c["check"]).startswith("provider_"))
    return {"status": "ok" if all_ok else "issues_found", "checks": checks}


@mcp.tool()
async def sift_get_config(key: str | None = None) -> dict:
    """Get sift configuration values.

    Args:
        key: Optional specific config key (dotted notation). Returns all config if omitted.
    """
    from sift.core.config_service import get_config_service

    svc = get_config_service()
    try:
        if key:
            value = svc.get(key)
            return {"status": "ok", "key": key, "value": value}
        return {"status": "ok", "config": svc.show()}
    except Exception as e:
        return {"status": "error", "error": str(e)}


@mcp.tool()
async def sift_set_config(key: str, value: str) -> dict:
    """Set a sift configuration value.

    Args:
        key: Config key in dotted notation (e.g., "providers.default").
        value: Value to set.
    """
    from sift.core.config_service import get_config_service

    svc = get_config_service()
    try:
        # Parse value types (same logic as config_cmd set_value)
        parsed_value: object
        if value.lower() in ("true", "yes", "1"):
            parsed_value = True
        elif value.lower() in ("false", "no", "0"):
            parsed_value = False
        else:
            try:
                parsed_value = int(value)
            except ValueError:
                parsed_value = value

        svc.set_global(key, parsed_value)
        return {"status": "ok", "key": key, "value": parsed_value}
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Migration tools
# ---------------------------------------------------------------------------


@mcp.tool()
async def sift_migrate(
    session_name: str | None = None,
    dry_run: bool = False,
) -> dict:
    """Run schema migrations on sessions and templates.

    Args:
        session_name: Optional specific session to migrate. Migrates all if omitted.
        dry_run: If true, preview changes without applying them.
    """
    from sift.core.migration_service import MigrationService

    svc = MigrationService()
    try:
        if session_name:
            result = svc.migrate_session(session_name, dry_run=dry_run)
            return {"status": "ok", "result": _serialize(result)}
        summary = svc.migrate_all(dry_run=dry_run)
        return {
            "status": "ok",
            "sessions": [_serialize(r) for r in summary.sessions],
            "templates": [_serialize(r) for r in summary.templates],
            "total_migrated": summary.total_migrated,
            "total_skipped": summary.total_skipped,
        }
    except Exception as e:
        return {"status": "error", "error": str(e)}


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main():
    """Run the sift MCP server via STDIO transport."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
