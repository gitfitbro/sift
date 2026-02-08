"""Custom exception hierarchy for sift.

All sift-specific exceptions derive from SiftError. Each exception
carries an optional ``context`` dict with structured metadata
(session name, phase ID, provider name, etc.) that the CLI error
handler can render.

Exception hierarchy::

    SiftError
    ├── SessionNotFoundError
    ├── PhaseNotFoundError
    ├── TemplateNotFoundError
    ├── ProviderError
    │   ├── ProviderAuthError
    │   ├── ProviderQuotaError
    │   ├── ProviderModelError
    │   └── ProviderUnavailableError
    ├── SchemaVersionError
    ├── ExtractionError
    ├── CaptureError
    └── ConfigError
"""
from __future__ import annotations

from typing import Optional


class SiftError(Exception):
    """Base class for all sift exceptions.

    Args:
        message: Human-readable error description.
        context: Optional dict of structured metadata.
    """

    exit_code: int = 1

    def __init__(self, message: str, context: Optional[dict] = None):
        self.context = context or {}
        super().__init__(message)


# ── Resource Not Found ─────────────────────────────────────────────

class SessionNotFoundError(SiftError):
    """Raised when a named session does not exist."""

    def __init__(self, session_name: str):
        super().__init__(
            f"Session '{session_name}' not found",
            context={"session": session_name},
        )


class PhaseNotFoundError(SiftError):
    """Raised when a phase ID does not exist in a session/template."""

    def __init__(
        self,
        phase_id: str,
        session_name: str = "",
        available: Optional[list[str]] = None,
    ):
        available_str = f". Available: {', '.join(available)}" if available else ""
        super().__init__(
            f"Phase '{phase_id}' not found{available_str}",
            context={"phase": phase_id, "session": session_name},
        )


class TemplateNotFoundError(SiftError):
    """Raised when a template cannot be found by name or path."""

    def __init__(self, template_name: str, search_dir: str = ""):
        msg = f"Template '{template_name}' not found"
        if search_dir:
            msg += f" in {search_dir}"
        super().__init__(msg, context={"template": template_name})


# ── Provider Errors ────────────────────────────────────────────────

class ProviderError(SiftError):
    """Base class for AI provider errors."""

    def __init__(
        self,
        message: str,
        provider: str = "",
        model: str = "",
        context: Optional[dict] = None,
    ):
        ctx = {"provider": provider, "model": model}
        if context:
            ctx.update(context)
        super().__init__(message, context=ctx)


class ProviderAuthError(ProviderError):
    """Raised when API key is missing or invalid."""
    pass


class ProviderQuotaError(ProviderError):
    """Raised when provider quota/rate limit is exceeded."""
    pass


class ProviderModelError(ProviderError):
    """Raised when the requested model is not found."""
    pass


class ProviderUnavailableError(ProviderError):
    """Raised when the provider cannot be reached or is not configured."""
    pass


# ── Schema Errors ──────────────────────────────────────────────────

class SchemaVersionError(SiftError):
    """Raised when a YAML file has an incompatible schema version."""

    def __init__(self, file_path: str, found_version: int, expected_version: int):
        super().__init__(
            f"Schema version mismatch in {file_path}: "
            f"found v{found_version}, expected v{expected_version}",
            context={
                "file": file_path,
                "found_version": found_version,
                "expected_version": expected_version,
            },
        )


# ── Operation Errors ───────────────────────────────────────────────

class ExtractionError(SiftError):
    """Raised when AI extraction fails."""

    def __init__(self, message: str, phase_id: str = "", session_name: str = ""):
        super().__init__(
            message,
            context={"phase": phase_id, "session": session_name},
        )


class CaptureError(SiftError):
    """Raised when file capture fails."""

    def __init__(self, message: str, phase_id: str = "", file_path: str = ""):
        super().__init__(
            message,
            context={"phase": phase_id, "file": file_path},
        )


class ConfigError(SiftError):
    """Raised when configuration is invalid or missing."""
    pass
