"""Service layer for sift.

All services return typed dataclasses. Services never import from sift.ui,
sift.cli, or typer. Consumer layers (CLI, TUI, MCP) handle presentation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


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
    depends_on: str | None = None


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
    captured_at: str | None = None
    source_document: str | None = None
    source_pages: str | None = None


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
    next_action: str | None = None
    next_action_phase: str | None = None


@dataclass
class CaptureResult:
    """Result of capturing content for a phase."""

    phase_id: str
    phase_name: str
    status: str  # "captured" or "transcribed"
    file_type: str  # "audio", "text", "pdf"
    char_count: int = 0
    pdf_stats: dict | None = None
    multi_phase_detected: bool = False
    appended: bool = False


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
    output_path: Path | None = None


@dataclass
class AnalysisSessionResult:
    """Result of creating a session from project analysis."""

    session_detail: SessionDetail
    analysis_path: Path
    populated_phases: list[str]
    template_name: str


@dataclass
class MigrationResult:
    """Result of a single migration operation."""

    name: str
    source_version: int
    target_version: int
    migrated: bool
    dry_run: bool = False
    changes: list[str] = field(default_factory=list)


@dataclass
class MigrationSummary:
    """Summary of a batch migration run."""

    sessions: list[MigrationResult] = field(default_factory=list)
    templates: list[MigrationResult] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def total_migrated(self) -> int:
        return sum(1 for r in self.sessions + self.templates if r.migrated)

    @property
    def total_skipped(self) -> int:
        return sum(1 for r in self.sessions + self.templates if not r.migrated)
