"""Unified CLI error handler for sift commands."""

from __future__ import annotations

import functools
import logging
import os
import traceback

import typer

from sift.errors import (
    ProviderAuthError,
    ProviderUnavailableError,
    SchemaVersionError,
    SessionNotFoundError,
    SiftError,
    TemplateNotFoundError,
)
from sift.ui import console

logger = logging.getLogger("sift.error_handler")


def _debug_mode() -> bool:
    """Check if debug output is enabled via SIFT_DEBUG env var."""
    return os.environ.get("SIFT_DEBUG", "").lower() in ("1", "true", "yes")


def _render_sift_error(e: SiftError) -> None:
    """Render a SiftError with Rich formatting and context."""
    console.print(f"\n[bold red]Error:[/bold red] {e}")

    # Context details (only in debug mode)
    if e.context and _debug_mode():
        context_parts = [
            f"  [dim]{key}:[/dim] {value}" for key, value in e.context.items() if value
        ]
        if context_parts:
            console.print("[dim]Context:[/dim]")
            for part in context_parts:
                console.print(part)

    # Actionable hints based on error type
    if isinstance(e, SessionNotFoundError):
        console.print("[dim]Run 'sift ls' to see available sessions.[/dim]")
    elif isinstance(e, TemplateNotFoundError):
        console.print("[dim]Run 'sift template list' to see available templates.[/dim]")
    elif isinstance(e, ProviderAuthError):
        console.print(
            "[dim]Run 'sift config set-key <provider> <key>' to store your API key.[/dim]"
        )
    elif isinstance(e, ProviderUnavailableError):
        console.print("[dim]Run 'sift doctor' to check your provider configuration.[/dim]")
    elif isinstance(e, SchemaVersionError):
        console.print(
            "[dim]This file was created by a newer version of sift. Please upgrade.[/dim]"
        )


def handle_errors(func):
    """Decorator that catches SiftError and renders formatted CLI output.

    Replaces scattered try/except blocks in command functions.
    Usage::

        @app.command()
        @handle_errors
        def my_command(...):
            ...  # no try/except needed
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except SiftError as e:
            _render_sift_error(e)
            if _debug_mode():
                console.print(f"\n[dim]{traceback.format_exc()}[/dim]")
            raise typer.Exit(e.exit_code)
        except KeyboardInterrupt:
            console.print("\n[dim]Interrupted.[/dim]")
            raise typer.Exit(130)
        except (typer.Exit, typer.Abort, SystemExit):
            raise
        except Exception as e:
            console.print(f"\n[bold red]Unexpected error:[/bold red] {e}")
            if _debug_mode():
                console.print(f"\n[dim]{traceback.format_exc()}[/dim]")
            else:
                console.print("[dim]Set SIFT_DEBUG=1 for full traceback.[/dim]")
            raise typer.Exit(1)

    return wrapper
