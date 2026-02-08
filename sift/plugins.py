"""Plugin discovery via setuptools entry points.

Third-party packages can register plugins by declaring entry points in their
``pyproject.toml``::

    [project.entry-points."sift.providers"]
    openai = "sift_openai:OpenAIProvider"

After ``pip install sift-openai``, the OpenAI provider appears automatically
in ``sift models`` and ``sift plugins``.

Entry point groups:
    sift.providers          - AI provider classes (must satisfy AIProvider protocol)
    sift.analyzers          - Project analysis strategies
    sift.output_formatters  - Output format handlers
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from importlib.metadata import entry_points
from typing import Any

logger = logging.getLogger("sift.plugins")

# Entry point group names
PROVIDER_GROUP = "sift.providers"
ANALYZER_GROUP = "sift.analyzers"
FORMATTER_GROUP = "sift.output_formatters"

ALL_GROUPS = [PROVIDER_GROUP, ANALYZER_GROUP, FORMATTER_GROUP]


@dataclass
class PluginInfo:
    """Metadata about a discovered plugin."""

    name: str
    group: str
    module: str
    loaded: bool = False
    error: str = ""
    instance: Any = field(default=None, repr=False)


def discover_plugins(group: str) -> dict[str, Any]:
    """Discover all registered plugins for a given entry point group.

    Args:
        group: Entry point group name (e.g. ``sift.providers``).

    Returns:
        Dict mapping plugin name to its loaded class/module.
    """
    plugins = {}
    eps = entry_points(group=group)
    for ep in eps:
        try:
            plugins[ep.name] = ep.load()
            logger.debug("Loaded plugin %s from %s", ep.name, ep.value)
        except Exception as e:
            logger.warning("Failed to load plugin %s: %s", ep.name, e)
    return plugins


def discover_providers() -> dict[str, type]:
    """Discover all registered AI providers via entry points."""
    return discover_plugins(PROVIDER_GROUP)


def discover_analyzers() -> dict[str, Any]:
    """Discover all registered project analyzers via entry points."""
    return discover_plugins(ANALYZER_GROUP)


def discover_formatters() -> dict[str, Any]:
    """Discover all registered output formatters via entry points."""
    return discover_plugins(FORMATTER_GROUP)


def list_all_plugins() -> list[PluginInfo]:
    """List all discovered plugins across all groups with load status.

    Returns:
        List of PluginInfo with load status for each plugin.
    """
    results = []
    for group in ALL_GROUPS:
        eps = entry_points(group=group)
        for ep in eps:
            info = PluginInfo(name=ep.name, group=group, module=ep.value)
            try:
                ep.load()
                info.loaded = True
            except Exception as e:
                info.error = str(e)
            results.append(info)
    return results


def get_provider_names() -> list[str]:
    """Get all registered provider names (for completions and validation).

    Returns:
        Sorted list of provider names.
    """
    eps = entry_points(group=PROVIDER_GROUP)
    return sorted(ep.name for ep in eps)
