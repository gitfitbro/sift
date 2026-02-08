"""Theme constants for Sift TUI, matching the Rich SIFT_THEME from ui.py."""

from __future__ import annotations

# Status icons (plain unicode, no Rich markup)
ICONS = {
    "complete": "\u2714",  # checkmark
    "active": "\u25b6",  # play triangle
    "pending": "\u25cb",  # empty circle
    "captured": "\u25c9",  # dotted circle
    "transcribed": "\u25c9",  # dotted circle
    "extracted": "\u25c9",  # dotted circle
    "error": "\u2718",  # cross
    "arrow": "\u2500\u2500\u25b8",  # ──▸
    "bullet": "\u2022",  # bullet
}

# Textual CSS color classes mapped from SIFT_THEME
STATUS_COLORS = {
    "complete": "green",
    "active": "cyan",
    "pending": "#808080",
    "captured": "yellow",
    "transcribed": "#1e90ff",
    "extracted": "green",
    "error": "red",
}
