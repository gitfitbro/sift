"""AI-powered project analysis.

Uses an AI provider to generate architecture summaries and
template recommendations from project structure data.
Falls back to heuristic recommendations when no provider is available.
"""
from __future__ import annotations

import logging
import yaml
from typing import Optional

from sift.providers.base import AIProvider
from .models import ProjectStructure, TemplateRecommendation

logger = logging.getLogger(__name__)

ARCHITECTURE_SYSTEM_PROMPT = """\
You are a senior software architect. Analyze the project structure and produce
a concise architecture summary (3-5 sentences). Focus on:
- What the project does (purpose)
- Key architectural patterns (MVC, microservices, CLI, etc.)
- Main entry points and data flow
- Notable frameworks and libraries

Be factual and specific. Do not speculate beyond what the structure shows."""

TEMPLATE_SYSTEM_PROMPT = """\
You are a session planning expert for the Sift CLI tool. Given a project
analysis, recommend a session template for reviewing/understanding this project.

A sift template has phases, each with:
- id: slug identifier
- name: human-readable name
- prompt: what to discuss/capture in this phase
- capture: [{type: "text", required: true}]
- extract: list of {id, type, prompt} fields to extract

Output valid YAML with this structure:
name: "<template-name>"
description: "<one-line description>"
phases:
  - id: "<phase-id>"
    name: "<Phase Name>"
    prompt: "<what to capture>"
    capture:
      - type: text
        required: true
    extract:
      - id: "<field-id>"
        type: "<text|list|boolean>"
        prompt: "<extraction prompt>"

Generate 3-5 phases appropriate for this project type. Focus on practical
review activities (architecture review, dependency audit, testing strategy, etc.).
Output ONLY valid YAML, no markdown fences."""


def generate_architecture_summary(
    structure: ProjectStructure,
    provider: AIProvider,
) -> str:
    """Use AI to generate an architecture summary for the project."""
    user_prompt = _build_structure_prompt(structure)
    try:
        return provider.chat(
            system=ARCHITECTURE_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=500,
        ).strip()
    except Exception as e:
        logger.warning("AI architecture summary failed: %s", e)
        return ""


def generate_template_recommendation(
    structure: ProjectStructure,
    provider: AIProvider,
) -> Optional[TemplateRecommendation]:
    """Use AI to generate a session template recommendation."""
    user_prompt = _build_structure_prompt(structure)
    try:
        raw = provider.chat(
            system=TEMPLATE_SYSTEM_PROMPT,
            user=f"Analyze this project and generate a sift session template:\n\n{user_prompt}",
            max_tokens=2000,
        ).strip()
    except Exception as e:
        logger.warning("AI template recommendation failed: %s", e)
        return _heuristic_recommendation(structure)

    return _parse_template_yaml(raw, structure)


def heuristic_recommendation(structure: ProjectStructure) -> TemplateRecommendation:
    """Generate a template recommendation using heuristics (no AI needed)."""
    return _heuristic_recommendation(structure)


def _build_structure_prompt(structure: ProjectStructure) -> str:
    """Build a concise prompt describing the project structure."""
    parts = [
        f"Project: {structure.name}",
        f"Total files: {structure.total_files}, Total lines: {structure.total_lines}",
    ]

    if structure.languages:
        lang_str = ", ".join(
            f"{lang}: {count}" for lang, count in
            sorted(structure.languages.items(), key=lambda x: -x[1])[:8]
        )
        parts.append(f"Languages: {lang_str}")

    if structure.frameworks_detected:
        parts.append(f"Frameworks: {', '.join(structure.frameworks_detected)}")

    if structure.entry_points:
        parts.append(f"Entry points: {', '.join(structure.entry_points[:5])}")

    if structure.dependencies:
        dep_names = [d.name for d in structure.dependencies[:20]]
        parts.append(f"Dependencies: {', '.join(dep_names)}")

    if structure.directory_tree:
        parts.append(f"\nDirectory structure:\n{structure.directory_tree}")

    # Include top files by complexity
    top_files = sorted(
        structure.file_analyses,
        key=lambda f: f.complexity_score,
        reverse=True,
    )[:10]
    if top_files:
        file_info = []
        for fa in top_files:
            rel = fa.path.relative_to(structure.root_path) if fa.path.is_relative_to(structure.root_path) else fa.path
            info = f"  {rel} ({fa.language}, {fa.line_count} lines"
            if fa.functions:
                info += f", {len(fa.functions)} functions"
            if fa.classes:
                info += f", {len(fa.classes)} classes"
            info += ")"
            file_info.append(info)
        parts.append(f"\nKey files:\n" + "\n".join(file_info))

    return "\n".join(parts)


def _parse_template_yaml(raw: str, structure: ProjectStructure) -> Optional[TemplateRecommendation]:
    """Parse AI-generated YAML into a TemplateRecommendation."""
    # Strip markdown fences if present
    cleaned = raw
    if "```" in cleaned:
        lines = cleaned.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(lines)

    try:
        data = yaml.safe_load(cleaned)
    except yaml.YAMLError as e:
        logger.warning("Failed to parse AI template YAML: %s", e)
        return _heuristic_recommendation(structure)

    if not isinstance(data, dict) or "phases" not in data:
        logger.warning("AI template missing 'phases' key")
        return _heuristic_recommendation(structure)

    return TemplateRecommendation(
        template_name=data.get("name", f"{structure.name}-review"),
        description=data.get("description", f"Review template for {structure.name}"),
        phases=data.get("phases", []),
        rationale=f"AI-generated based on {structure.total_files} files across "
                  f"{len(structure.languages)} languages",
    )


def _heuristic_recommendation(structure: ProjectStructure) -> TemplateRecommendation:
    """Generate a basic template recommendation from project structure heuristics."""
    phases = []

    # Phase 1: Architecture overview (always)
    phases.append({
        "id": "architecture-overview",
        "name": "Architecture Overview",
        "prompt": f"Review the overall architecture of {structure.name}. "
                  "Discuss the main components, data flow, and design patterns used.",
        "capture": [{"type": "text", "required": True}],
        "extract": [
            {"id": "patterns", "type": "list", "prompt": "List the architectural patterns identified."},
            {"id": "components", "type": "list", "prompt": "List the main components/modules."},
        ],
    })

    # Phase 2: Dependency audit (if dependencies found)
    if structure.dependencies:
        phases.append({
            "id": "dependency-audit",
            "name": "Dependency Audit",
            "prompt": f"Review the {len(structure.dependencies)} dependencies. "
                      "Identify any outdated, unused, or risky dependencies.",
            "capture": [{"type": "text", "required": True}],
            "extract": [
                {"id": "risks", "type": "list", "prompt": "List dependency risks or concerns."},
                {"id": "recommendations", "type": "list", "prompt": "List dependency recommendations."},
            ],
        })

    # Phase 3: Code quality (always)
    phases.append({
        "id": "code-quality",
        "name": "Code Quality Review",
        "prompt": "Assess code quality: naming conventions, documentation coverage, "
                  "complexity hotspots, and testing practices.",
        "capture": [{"type": "text", "required": True}],
        "extract": [
            {"id": "issues", "type": "list", "prompt": "List code quality issues found."},
            {"id": "strengths", "type": "list", "prompt": "List code quality strengths."},
        ],
    })

    # Phase 4: Testing strategy (if test files detected)
    has_tests = any(
        "test" in str(fa.path).lower() for fa in structure.file_analyses
    )
    if has_tests:
        phases.append({
            "id": "testing-strategy",
            "name": "Testing Strategy",
            "prompt": "Review the testing approach: coverage, test types (unit, integration, e2e), "
                      "and gaps in test coverage.",
            "capture": [{"type": "text", "required": True}],
            "extract": [
                {"id": "coverage_gaps", "type": "list", "prompt": "List areas with missing test coverage."},
                {"id": "test_quality", "type": "text", "prompt": "Assess overall test quality."},
            ],
        })

    # Phase 5: Action items (always)
    phases.append({
        "id": "action-items",
        "name": "Action Items & Recommendations",
        "prompt": "Summarize findings and prioritize action items for improvement.",
        "capture": [{"type": "text", "required": True}],
        "extract": [
            {"id": "priorities", "type": "list", "prompt": "List prioritized action items."},
            {"id": "quick_wins", "type": "list", "prompt": "List quick wins that can be done immediately."},
        ],
    })

    primary_lang = max(structure.languages, key=structure.languages.get) if structure.languages else "unknown"

    return TemplateRecommendation(
        template_name=f"{structure.name}-review",
        description=f"Code review template for {structure.name} ({primary_lang} project)",
        phases=phases,
        rationale=f"Heuristic template based on {structure.total_files} files, "
                  f"{len(structure.dependencies)} dependencies, "
                  f"primary language: {primary_lang}",
    )
