"""Service layer for sift.

All services return typed dataclasses. Services never import from sift.ui,
sift.cli, or typer. Consumer layers (CLI, TUI, MCP) handle presentation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class TemplateInfo:
    """Summary info for template listing."""
    name: str
    stem: str
    description: str
    phase_count: int
    output_count: int


@dataclass
class TemplatePhaseDetail:
    """Detailed phase info for template display."""
    id: str
    name: str
    prompt: str
    capture_types: list[str]
    required: bool
    extract_field_ids: list[str]
    depends_on: Optional[str] = None


@dataclass
class TemplateDetail:
    """Full template detail for display."""
    name: str
    description: str
    phases: list[TemplatePhaseDetail]
    outputs: list[dict]


@dataclass
class SessionInfo:
    """Summary info for session listing."""
    name: str
    template_name: str
    status: str
    total_phases: int
    done_phases: int
    in_progress_phases: int
    updated_at: str


@dataclass
class PhaseDetail:
    """Phase detail for session status."""
    id: str
    name: str
    status: str
    has_audio: bool
    has_transcript: bool
    has_extracted: bool
    captured_at: Optional[str] = None
    source_document: Optional[str] = None
    source_pages: Optional[str] = None


@dataclass
class SessionDetail:
    """Full session detail for status display."""
    name: str
    template_name: str
    status: str
    created_at: str
    updated_at: str
    total_phases: int
    done_phases: int
    phases: list[PhaseDetail]
    next_action: Optional[str] = None
    next_action_phase: Optional[str] = None


@dataclass
class CaptureResult:
    """Result of capturing content for a phase."""
    phase_id: str
    phase_name: str
    status: str  # "captured" or "transcribed"
    file_type: str  # "audio", "text", "pdf"
    char_count: int = 0
    pdf_stats: Optional[dict] = None
    multi_phase_detected: bool = False


@dataclass
class TranscribeResult:
    """Result of transcribing audio."""
    phase_id: str
    char_count: int
    transcript_preview: str


@dataclass
class ExtractionResult:
    """Result of structured data extraction."""
    phase_id: str
    phase_name: str
    fields: dict
    field_count: int


@dataclass
class BuildResult:
    """Result of generating outputs."""
    generated_files: list[tuple[str, Path]]
    output_dir: Path


@dataclass
class ExportData:
    """Exported session data."""
    data: dict
    output_path: Optional[Path] = None
