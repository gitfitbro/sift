"""Shell completion functions for Sift CLI."""
from __future__ import annotations


def complete_session_name(incomplete: str) -> list[str]:
    """Complete session names from filesystem."""
    from sift.core.session_service import SessionService
    return [n for n in SessionService().get_session_names() if n.startswith(incomplete)]


def complete_template_name(incomplete: str) -> list[str]:
    """Complete template names. Handles '+' syntax for multi-template."""
    from sift.core.session_service import SessionService
    names = SessionService().get_template_names()
    if "+" in incomplete:
        prefix = incomplete.rsplit("+", 1)[0] + "+"
        partial = incomplete.rsplit("+", 1)[1]
        return [prefix + n for n in names if n.startswith(partial)]
    return [n for n in names if n.startswith(incomplete)]


def complete_phase_id(ctx, incomplete: str) -> list[str]:
    """Context-aware phase ID completion (reads session from parsed args)."""
    from sift.core.session_service import SessionService
    session_name = ctx.params.get("session")
    if not session_name:
        return []
    return [p for p in SessionService().get_phase_ids(session_name) if p.startswith(incomplete)]


def complete_provider_name(incomplete: str) -> list[str]:
    """Complete provider names."""
    return [p for p in ["anthropic", "gemini", "ollama"] if p.startswith(incomplete)]


def complete_format(incomplete: str) -> list[str]:
    """Complete output format names."""
    return [f for f in ["yaml", "markdown", "all"] if f.startswith(incomplete)]
