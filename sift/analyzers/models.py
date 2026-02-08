"""Data models for project analysis results."""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


@dataclass
class FileAnalysis:
    """Analysis result for a single source file."""
    path: Path
    language: str
    line_count: int
    functions: list[str] = field(default_factory=list)
    classes: list[str] = field(default_factory=list)
    imports: list[str] = field(default_factory=list)
    complexity_score: float = 0.0
    doc_coverage: float = 0.0


@dataclass
class DependencyInfo:
    """A project dependency detected from manifest files."""
    name: str
    version: str = ""
    source: str = ""  # e.g. "pyproject.toml", "package.json"


@dataclass
class ProjectStructure:
    """Complete analysis of a software project."""
    root_path: Path
    name: str
    languages: dict[str, int] = field(default_factory=dict)  # language -> file count
    total_files: int = 0
    total_lines: int = 0
    file_analyses: list[FileAnalysis] = field(default_factory=list)
    dependencies: list[DependencyInfo] = field(default_factory=list)
    entry_points: list[str] = field(default_factory=list)
    frameworks_detected: list[str] = field(default_factory=list)
    directory_tree: str = ""
    architecture_summary: str = ""  # AI-generated


@dataclass
class TemplateRecommendation:
    """A recommended sift session template based on project analysis."""
    template_name: str
    description: str
    phases: list[dict] = field(default_factory=list)
    rationale: str = ""
