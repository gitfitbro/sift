"""AI-powered document analysis for multi-phase content detection and routing."""
from __future__ import annotations
import re
import yaml
from dataclasses import dataclass
from typing import Optional
from sift.ui import console
from sift.providers import get_provider


@dataclass
class PhaseMapping:
    """Result of mapping a document section to a template phase."""
    phase_id: str
    phase_name: str
    matched_pages: str        # "1-3", "4-6", "all"
    section_title: str        # what was detected, e.g., "Workflow Description"
    confidence: str           # "high", "medium", "low"
    content: str = ""         # the actual extracted text for this phase


def analyze_document_for_phases(
    document_text: str,
    phases: list,
    template_name: str = "",
) -> list[PhaseMapping]:
    """Use AI to map document sections to template phases.

    Args:
        document_text: Full text with [Page N] markers
        phases: List of PhaseTemplate objects from the template
        template_name: Name of the template (for context)

    Returns:
        List of PhaseMapping objects for phases that have matching content.
    """
    try:
        provider = get_provider()
        if not provider.is_available():
            raise ValueError("not available")
    except ValueError:
        console.print("[yellow]No AI provider configured. Cannot analyze document.[/yellow]")
        return []

    # Build phase descriptions for the prompt
    phase_descriptions = []
    for p in phases:
        fields_desc = ""
        if p.extract:
            fields_desc = "\n".join(
                f"    - {e.id} ({e.type}): {e.prompt}"
                for e in p.extract
            )
        phase_descriptions.append(
            f"### Phase: {p.name} (id: {p.id})\n"
            f"Description: {p.prompt.strip()}\n"
            f"Extraction fields:\n{fields_desc}" if fields_desc else
            f"### Phase: {p.name} (id: {p.id})\n"
            f"Description: {p.prompt.strip()}"
        )

    phases_text = "\n\n".join(phase_descriptions)

    # Truncate document if very long (preserve page markers)
    doc_for_analysis = document_text
    if len(doc_for_analysis) > 15000:
        doc_for_analysis = doc_for_analysis[:15000] + "\n\n[... document truncated for analysis ...]"

    system_prompt = (
        "You are a document analysis engine for a structured session capture tool. "
        "You will be given a document with [Page N] markers and a list of session phases. "
        "Each phase has a name, description, and extraction fields.\n\n"
        "Your job is to determine which pages/sections of the document correspond to which phases "
        "based on semantic content matching.\n\n"
        "Rules:\n"
        "- A page can only belong to one phase\n"
        "- Pages should be contiguous ranges per phase (e.g., 1-3, not 1,3,5)\n"
        "- Some phases may not have matching content -- omit them\n"
        "- Some pages may not match any phase -- note them as unmatched\n"
        "- Base your matching on the phase descriptions and extraction field definitions\n"
        "- Return results as valid YAML only, no markdown fences, no preamble"
    )

    user_prompt = f"""## Document Content
<document>
{doc_for_analysis}
</document>

## Template: {template_name}

## Session Phases
{phases_text}

## Instructions
Map document sections to phases. Return YAML with this exact structure:

phases:
  - phase_id: "the_phase_id"
    matched_pages: "N-M"
    section_title: "descriptive name of the matching section"
    confidence: "high"
unmatched_pages: "N-M"

Only include phases that have actual matching content. Omit phases with no match."""

    console.print(f"[dim]Analyzing document with {provider.name} ({provider.model})...[/dim]")

    try:
        response_text = provider.chat(system_prompt, user_prompt, max_tokens=4000).strip()
    except (RuntimeError, Exception) as e:
        console.print(f"[red]Provider error: {e}[/red]")
        return []

    # Clean up response
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        response_text = "\n".join(lines)

    # Parse YAML response
    try:
        result = yaml.safe_load(response_text)
    except yaml.YAMLError:
        console.print("[dim]Fixing YAML formatting...[/dim]")
        try:
            fix_prompt = (
                "The following YAML has syntax errors. Fix it and return ONLY valid YAML:\n\n"
                f"{response_text}"
            )
            fixed_text = provider.chat("", fix_prompt, max_tokens=4000).strip()
            if fixed_text.startswith("```"):
                lines = fixed_text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                fixed_text = "\n".join(lines)
            result = yaml.safe_load(fixed_text)
        except (yaml.YAMLError, Exception):
            console.print("[yellow]Could not parse analysis response.[/yellow]")
            return []

    if not isinstance(result, dict) or "phases" not in result:
        return []

    # Build PhaseMapping objects
    phase_lookup = {p.id: p.name for p in phases}
    mappings = []

    for entry in result.get("phases", []):
        pid = entry.get("phase_id", "")
        if pid not in phase_lookup:
            continue

        pages_str = str(entry.get("matched_pages", ""))
        section = entry.get("section_title", "")
        confidence = entry.get("confidence", "medium")

        # Extract actual content for these pages
        content = _extract_pages(document_text, pages_str)

        mappings.append(PhaseMapping(
            phase_id=pid,
            phase_name=phase_lookup[pid],
            matched_pages=pages_str,
            section_title=section,
            confidence=confidence,
            content=content,
        ))

    return mappings


def split_document_by_pages(document_text: str, page_ranges: dict[str, str]) -> dict[str, str]:
    """Split document text into per-phase content based on page range assignments.

    Args:
        document_text: Full text with [Page N] markers
        page_ranges: Dict mapping phase_id -> "1-3" page range strings

    Returns:
        Dict mapping phase_id -> extracted text for those pages
    """
    result = {}
    for phase_id, pages_str in page_ranges.items():
        result[phase_id] = _extract_pages(document_text, pages_str)
    return result


def _extract_pages(document_text: str, pages_str: str) -> str:
    """Extract content for specific pages from document text with [Page N] markers."""
    if not pages_str or pages_str.lower() == "all":
        return document_text

    # Parse page range (e.g., "1-3", "4", "5-8")
    target_pages = set()
    for part in pages_str.split(","):
        part = part.strip()
        if "-" in part:
            start, end = part.split("-", 1)
            try:
                target_pages.update(range(int(start.strip()), int(end.strip()) + 1))
            except ValueError:
                continue
        else:
            try:
                target_pages.add(int(part))
            except ValueError:
                continue

    if not target_pages:
        return document_text

    # Split by [Page N] markers and collect matching pages
    page_pattern = re.compile(r'\[Page (\d+)\]')
    pages = page_pattern.split(document_text)

    # pages alternates: [text_before_first_marker, page_num, page_content, page_num, page_content, ...]
    collected = []
    i = 1  # skip text before first marker
    while i < len(pages) - 1:
        try:
            page_num = int(pages[i])
        except ValueError:
            i += 2
            continue

        if page_num in target_pages:
            collected.append(f"[Page {page_num}]\n{pages[i + 1].strip()}")

        i += 2

    return "\n\n".join(collected) if collected else ""


def detect_multi_phase_content(document_text: str, phases: list) -> bool:
    """Quick heuristic check: does this document likely cover multiple phases?

    Uses keyword matching against phase names, prompts, and extraction field descriptions.
    No AI call - this is for the suggestion hint in `sift phase capture`.

    Args:
        document_text: The full extracted text from the document
        phases: List of PhaseTemplate objects

    Returns:
        True if the document likely covers 2+ phases
    """
    if len(phases) < 2:
        return False

    doc_lower = document_text.lower()
    phases_matched = 0

    for phase in phases:
        # Build keyword set from phase name, prompt, and extraction fields
        keywords = set()

        # Phase name words (split on spaces, skip short words)
        for word in phase.name.lower().split():
            if len(word) > 3:
                keywords.add(word)

        # Extraction field IDs and key words from prompts
        if phase.extract:
            for field in phase.extract:
                # Field ID (replace underscores with spaces)
                for word in field.id.replace("_", " ").lower().split():
                    if len(word) > 3:
                        keywords.add(word)
                # Key words from field prompt
                for word in field.prompt.lower().split():
                    if len(word) > 4:
                        keywords.add(word)

        if not keywords:
            continue

        # Count how many keywords match
        matches = sum(1 for kw in keywords if kw in doc_lower)
        match_ratio = matches / len(keywords) if keywords else 0

        # A phase is "covered" if >30% of its keywords appear
        if match_ratio > 0.3:
            phases_matched += 1

    return phases_matched >= 2
