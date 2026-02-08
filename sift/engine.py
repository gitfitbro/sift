"""AI engine for transcription and structured extraction."""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

import yaml

from sift.providers import get_provider

logger = logging.getLogger("sift.engine")


from sift.errors import ProviderUnavailableError

# Backward-compatible alias
NoProviderError = ProviderUnavailableError


def transcribe_audio(audio_path: Path) -> str:
    """
    Transcribe audio file to text.

    Strategy:
    1. If active AI provider supports audio, use it
    2. Fall back to local whisper if installed
    3. Raise NoProviderError (caller handles manual fallback)
    """
    if not audio_path.exists():
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    # Ensure we have a compatible format (convert to mp3 if needed)
    mp3_path = audio_path.with_suffix(".mp3")
    if audio_path.suffix != ".mp3":
        logger.info("Converting %s to mp3...", audio_path.suffix)
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
            logger.warning(
                "%s transcription not available. Trying fallbacks...",
                provider.name,
            )
    except ProviderUnavailableError:
        pass  # No provider configured

    # Try local whisper
    if _whisper_available():
        return _transcribe_with_whisper(mp3_path)

    # No automated option available
    raise ProviderUnavailableError(
        "No transcription method available. Options:\n"
        "  1. Set AI_PROVIDER and API key in .env\n"
        "  2. Install whisper: pip install openai-whisper\n"
        "  3. Paste the transcript manually",
    )


def _whisper_available() -> bool:
    """Check if local whisper is installed."""
    try:
        import whisper  # noqa: F401

        return True
    except ImportError:
        return False


def _transcribe_with_whisper(audio_path: Path) -> str:
    """Transcribe using local whisper model."""
    import whisper

    logger.info("Transcribing with local Whisper model...")
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

    Raises:
        ProviderUnavailableError: If no AI provider is available.
    """
    try:
        provider = get_provider()
        if not provider.is_available():
            raise ProviderUnavailableError("Provider not available")
    except ProviderUnavailableError:
        raise ProviderUnavailableError(
            "No AI provider configured for extraction.",
        )

    # Build the extraction prompt
    field_descriptions = []
    for f in extraction_fields:
        field_descriptions.append(f"- **{f['id']}** (type: {f['type']}): {f['prompt']}")

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

    logger.info("Extracting with %s (%s)...", provider.name, provider.model)

    try:
        response_text = provider.chat(system_prompt, user_prompt, max_tokens=8000).strip()
    except (RuntimeError, Exception) as e:
        logger.error("Provider error during extraction: %s", e)
        raise

    # Clean up response (remove markdown fences if present)
    response_text = _strip_markdown_fences(response_text)

    try:
        extracted = yaml.safe_load(response_text)
        if not isinstance(extracted, dict):
            extracted = {"raw": extracted}
        return extracted
    except yaml.YAMLError:
        # YAML parse failed — ask the provider to fix it
        logger.info("Fixing YAML formatting...")
        try:
            fix_prompt = (
                "The following YAML has syntax errors (likely unquoted colons in values). "
                "Fix it and return ONLY valid YAML. Quote any string values that contain colons.\n\n"
                f"{response_text}"
            )
            fixed_text = provider.chat("", fix_prompt, max_tokens=8000).strip()
            fixed_text = _strip_markdown_fences(fixed_text)
            extracted = yaml.safe_load(fixed_text)
            if not isinstance(extracted, dict):
                extracted = {"raw": extracted}
            return extracted
        except (yaml.YAMLError, Exception):
            logger.warning("Could not parse extraction as YAML. Saving raw response.")
            return {"_raw_response": response_text}


def generate_summary(
    session_data: dict,
    template_name: str = "",
) -> str:
    """Generate a natural language summary of a complete session."""
    try:
        provider = get_provider()
        if not provider.is_available():
            raise ProviderUnavailableError("Provider not available")
    except ProviderUnavailableError:
        return _generate_summary_local(session_data)

    data_yaml = yaml.dump(session_data, default_flow_style=False, sort_keys=False)

    user_prompt = (
        f"Here is the structured data captured from a '{template_name}' session:\n\n"
        f"{data_yaml}\n\n"
        "Please generate a clear, professional summary of this session. "
        "Include key findings, identified gaps, and recommended next steps. "
        "Write in prose, not bullet points. Be concise but thorough."
    )

    logger.info("Generating summary with %s...", provider.name)
    try:
        return provider.chat("", user_prompt, max_tokens=4000)
    except (RuntimeError, Exception) as e:
        logger.error("Provider error during summary: %s", e)
        logger.warning("Falling back to local summary.")
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


def _strip_markdown_fences(text: str) -> str:
    """Remove markdown code fences from text."""
    if text.startswith("```"):
        lines = text.split("\n")
        lines = [line for line in lines if not line.strip().startswith("```")]
        text = "\n".join(lines)
    return text
