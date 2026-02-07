"""AI engine for transcription and structured extraction."""
from __future__ import annotations
import os
import yaml
import subprocess
from pathlib import Path
from typing import Optional
from sift.ui import console
from sift.providers import get_provider


def transcribe_audio(audio_path: Path) -> str:
    """
    Transcribe audio file to text.

    Strategy:
    1. If active AI provider supports audio, use it
    2. Fall back to local whisper if installed
    3. Fall back to prompting user to paste transcript
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Ensure we have a compatible format (convert to mp3 if needed)
    mp3_path = audio_path.with_suffix(".mp3")
    if audio_path.suffix != ".mp3":
        console.print(f"[dim]Converting {audio_path.suffix} to mp3...[/dim]")
        subprocess.run(
            ["ffmpeg", "-i", str(audio_path), "-q:a", "2", str(mp3_path), "-y"],
            capture_output=True,
        )
    else:
        mp3_path = audio_path

    # Try active AI provider
    try:
        provider = get_provider()
        if provider.is_available():
            result = provider.transcribe(mp3_path)
            if result is not None:
                return result
            console.print(f"[yellow]{provider.name} transcription not available. Trying fallbacks...[/yellow]")
    except ValueError:
        pass  # No provider configured

    # Try local whisper
    if _whisper_available():
        return _transcribe_with_whisper(mp3_path)

    # Fall back to manual
    console.print("[yellow]No transcription API configured.[/yellow]")
    console.print("Options:")
    console.print("  1. Set AI_PROVIDER and API key in .env")
    console.print("  2. Install whisper: pip install openai-whisper")
    console.print("  3. Paste the transcript manually below")
    console.print()

    text = console.input("[bold]Paste transcript (Ctrl+D when done):[/bold]\n")
    return text


def _whisper_available() -> bool:
    """Check if local whisper is installed."""
    try:
        import whisper
        return True
    except ImportError:
        return False


def _transcribe_with_whisper(audio_path: Path) -> str:
    """Transcribe using local whisper model."""
    import whisper

    console.print("[dim]Transcribing with local Whisper model...[/dim]")
    model = whisper.load_model("base")
    result = model.transcribe(str(audio_path))
    return result["text"]


def extract_structured_data(
    transcript: str,
    extraction_fields: list[dict],
    phase_name: str = "",
    context: str = "",
) -> dict:
    """
    Extract structured data from a transcript using the active AI provider.

    Args:
        transcript: The raw transcript text
        extraction_fields: List of {id, type, prompt} dicts defining what to extract
        phase_name: Name of the current phase (for context)
        context: Additional context from previous phases

    Returns:
        Dict with extraction field IDs as keys and extracted data as values
    """
    try:
        provider = get_provider()
        if not provider.is_available():
            raise ValueError("not available")
    except ValueError:
        console.print("[yellow]No AI provider configured. Falling back to manual extraction.[/yellow]")
        return _manual_extraction(extraction_fields)

    # Build the extraction prompt
    field_descriptions = []
    for f in extraction_fields:
        field_descriptions.append(
            f"- **{f['id']}** (type: {f['type']}): {f['prompt']}"
        )

    fields_text = "\n".join(field_descriptions)

    system_prompt = (
        "You are a structured data extraction engine. Given a transcript, "
        "extract the requested information and return it as valid YAML. "
        "Be thorough but precise. Only include information that is actually "
        "present in or clearly implied by the transcript. "
        "Do not invent or assume information not supported by the text."
    )

    user_prompt = f"""Here is a transcript from the "{phase_name}" phase of a session:

<transcript>
{transcript}
</transcript>

{f"Additional context from previous phases: {context}" if context else ""}

Please extract the following structured data from this transcript:

{fields_text}

Return your response as valid YAML with each field ID as a top-level key.
For 'list' types, use YAML lists. For 'map' types, use YAML mappings.
For 'text' types, use plain strings. For 'boolean' types, use true/false.

Return ONLY the YAML, no markdown fences, no preamble, no explanation."""

    console.print(f"[dim]Extracting with {provider.name} ({provider.model})...[/dim]")

    try:
        response_text = provider.chat(system_prompt, user_prompt, max_tokens=8000).strip()
    except (RuntimeError, Exception) as e:
        console.print(f"[red]Provider error: {e}[/red]")
        console.print("[yellow]Falling back to manual extraction.[/yellow]")
        return _manual_extraction(extraction_fields)

    # Clean up response (remove markdown fences if present)
    if response_text.startswith("```"):
        lines = response_text.split("\n")
        lines = [l for l in lines if not l.strip().startswith("```")]
        response_text = "\n".join(lines)

    try:
        extracted = yaml.safe_load(response_text)
        if not isinstance(extracted, dict):
            extracted = {"raw": extracted}
        return extracted
    except yaml.YAMLError:
        # YAML parse failed — ask the provider to fix it
        console.print("[dim]Fixing YAML formatting...[/dim]")
        try:
            fix_prompt = (
                "The following YAML has syntax errors (likely unquoted colons in values). "
                "Fix it and return ONLY valid YAML. Quote any string values that contain colons.\n\n"
                f"{response_text}"
            )
            fixed_text = provider.chat("", fix_prompt, max_tokens=8000).strip()
            if fixed_text.startswith("```"):
                lines = fixed_text.split("\n")
                lines = [l for l in lines if not l.strip().startswith("```")]
                fixed_text = "\n".join(lines)
            extracted = yaml.safe_load(fixed_text)
            if not isinstance(extracted, dict):
                extracted = {"raw": extracted}
            return extracted
        except (yaml.YAMLError, Exception):
            console.print("[yellow]Warning: Could not parse extraction as YAML. Saving raw response.[/yellow]")
            return {"_raw_response": response_text}


def _manual_extraction(extraction_fields: list[dict]) -> dict:
    """Fall back to manual data entry for extraction fields."""
    result = {}
    console.print("\n[bold]Manual extraction mode.[/bold] Enter data for each field:\n")

    for f in extraction_fields:
        console.print(f"[bold]{f['id']}[/bold] ({f['type']}): {f['prompt']}")

        if f["type"] == "list":
            console.print("[dim]Enter items one per line. Empty line to finish.[/dim]")
            items = []
            while True:
                item = input("  > ").strip()
                if not item:
                    break
                items.append(item)
            result[f["id"]] = items
        elif f["type"] == "boolean":
            val = input("  (y/n): ").strip().lower()
            result[f["id"]] = val in ("y", "yes", "true", "1")
        elif f["type"] == "map":
            console.print("[dim]Enter key: value pairs. Empty line to finish.[/dim]")
            mapping = {}
            while True:
                line = input("  > ").strip()
                if not line:
                    break
                if ":" in line:
                    k, v = line.split(":", 1)
                    mapping[k.strip()] = v.strip()
            result[f["id"]] = mapping
        else:
            result[f["id"]] = input("  > ").strip()

        console.print()

    return result


def generate_summary(
    session_data: dict,
    template_name: str = "",
) -> str:
    """Generate a natural language summary of a complete session."""
    try:
        provider = get_provider()
        if not provider.is_available():
            raise ValueError("not available")
    except ValueError:
        return _generate_summary_local(session_data)

    data_yaml = yaml.dump(session_data, default_flow_style=False, sort_keys=False)

    user_prompt = (
        f"Here is the structured data captured from a '{template_name}' session:\n\n"
        f"{data_yaml}\n\n"
        "Please generate a clear, professional summary of this session. "
        "Include key findings, identified gaps, and recommended next steps. "
        "Write in prose, not bullet points. Be concise but thorough."
    )

    console.print(f"[dim]Generating summary with {provider.name}...[/dim]")
    try:
        return provider.chat("", user_prompt, max_tokens=4000)
    except (RuntimeError, Exception) as e:
        console.print(f"[red]Provider error: {e}[/red]")
        console.print("[yellow]Falling back to local summary.[/yellow]")
        return _generate_summary_local(session_data)


def _generate_summary_local(session_data: dict) -> str:
    """Generate a basic summary without AI."""
    lines = ["# Session Summary\n"]
    for phase_id, data in session_data.items():
        lines.append(f"## {phase_id}\n")
        if isinstance(data, dict):
            for k, v in data.items():
                if isinstance(v, list):
                    lines.append(f"### {k}")
                    for item in v:
                        lines.append(f"- {item}")
                elif isinstance(v, dict):
                    lines.append(f"### {k}")
                    for mk, mv in v.items():
                        lines.append(f"- **{mk}**: {mv}")
                else:
                    lines.append(f"**{k}**: {v}")
                lines.append("")
        lines.append("")
    return "\n".join(lines)
