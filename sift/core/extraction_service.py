"""Extraction service - business logic for capture, transcription, and extraction."""
from __future__ import annotations

import logging
import shutil
import yaml
from datetime import datetime
from pathlib import Path
from typing import Optional

from sift.core import CaptureResult, TranscribeResult, ExtractionResult
from sift.models import ensure_dirs, Session

logger = logging.getLogger("sift.core.extraction")

# File type classifications
AUDIO_EXTENSIONS = {".mp3", ".wav", ".webm", ".m4a", ".ogg", ".flac", ".mp4", ".aac"}
TEXT_EXTENSIONS = {".txt", ".md", ".text"}
PDF_EXTENSIONS = {".pdf"}


class ExtractionService:
    """Handles capture, transcription, and structured data extraction."""

    def capture_file(
        self, session_name: str, phase_id: str, file_path: Path
    ) -> CaptureResult:
        """Capture a file (audio, text, or PDF) for a session phase.

        Raises:
            FileNotFoundError: If session or file not found.
            ValueError: If phase not found or unsupported file type.
        """
        ensure_dirs()
        s = Session.load(session_name)
        tmpl = s.get_template()

        pt = next((p for p in tmpl.phases if p.id == phase_id), None)
        if not pt:
            raise ValueError(
                f"Phase '{phase_id}' not found. "
                f"Available: {', '.join(p.id for p in tmpl.phases)}"
            )

        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        ps = s.phases[phase_id]
        phase_dir = s.phase_dir(phase_id)
        suffix = file_path.suffix.lower()
        now = datetime.now().isoformat()

        if suffix in AUDIO_EXTENSIONS:
            dest = phase_dir / f"audio{suffix}"
            shutil.copy2(file_path, dest)
            ps.audio_file = dest.name
            ps.status = "captured"
            ps.captured_at = now
            s.save()
            logger.info("Audio captured for %s: %s", phase_id, dest.name)
            return CaptureResult(
                phase_id=phase_id,
                phase_name=pt.name,
                status="captured",
                file_type="audio",
            )

        elif suffix in TEXT_EXTENSIONS:
            dest = phase_dir / "transcript.txt"
            shutil.copy2(file_path, dest)
            ps.transcript_file = dest.name
            ps.status = "transcribed"
            ps.captured_at = now
            ps.transcribed_at = now
            s.save()
            char_count = dest.read_text().__len__()
            logger.info("Text captured for %s: %d chars", phase_id, char_count)
            return CaptureResult(
                phase_id=phase_id,
                phase_name=pt.name,
                status="transcribed",
                file_type="text",
                char_count=char_count,
            )

        elif suffix in PDF_EXTENSIONS:
            return self._capture_pdf(s, pt, ps, phase_dir, file_path, now)

        else:
            supported = AUDIO_EXTENSIONS | TEXT_EXTENSIONS | PDF_EXTENSIONS
            raise ValueError(
                f"Unsupported file type: {suffix}. "
                f"Supported: {', '.join(sorted(supported))}"
            )

    def capture_text(
        self, session_name: str, phase_id: str, text: str
    ) -> CaptureResult:
        """Capture text content directly for a session phase.

        Raises:
            FileNotFoundError: If session not found.
            ValueError: If phase not found or text is empty.
        """
        ensure_dirs()
        s = Session.load(session_name)
        tmpl = s.get_template()

        pt = next((p for p in tmpl.phases if p.id == phase_id), None)
        if not pt:
            raise ValueError(f"Phase '{phase_id}' not found")

        if not text.strip():
            raise ValueError("No text provided")

        ps = s.phases[phase_id]
        phase_dir = s.phase_dir(phase_id)
        now = datetime.now().isoformat()

        dest = phase_dir / "transcript.txt"
        dest.write_text(text)
        ps.transcript_file = dest.name
        ps.status = "transcribed"
        ps.captured_at = now
        ps.transcribed_at = now
        s.save()

        logger.info("Text captured for %s: %d chars", phase_id, len(text))
        return CaptureResult(
            phase_id=phase_id,
            phase_name=pt.name,
            status="transcribed",
            file_type="text",
            char_count=len(text),
        )

    def check_multi_phase(self, session_name: str, pdf_text: str) -> bool:
        """Check if PDF text covers multiple phases of a session's template."""
        from sift.document_analyzer import detect_multi_phase_content

        s = Session.load(session_name)
        tmpl = s.get_template()
        if len(tmpl.phases) < 2:
            return False
        return detect_multi_phase_content(pdf_text, tmpl.phases)

    def transcribe_phase(self, session_name: str, phase_id: str) -> TranscribeResult:
        """Transcribe audio for a phase using the active AI provider.

        Raises:
            FileNotFoundError: If session not found.
            ValueError: If phase not found, no audio, or already transcribed.
        """
        ensure_dirs()
        s = Session.load(session_name)

        ps = s.phases.get(phase_id)
        if not ps:
            raise ValueError(f"Phase '{phase_id}' not found")
        if not ps.audio_file:
            raise ValueError(f"No audio file for phase '{phase_id}'")

        audio_path = s.phase_dir(phase_id) / ps.audio_file

        from sift.engine import transcribe_audio
        transcript = transcribe_audio(audio_path)

        dest = s.phase_dir(phase_id) / "transcript.txt"
        dest.write_text(transcript)

        ps.transcript_file = dest.name
        ps.status = "transcribed"
        ps.transcribed_at = datetime.now().isoformat()
        s.save()

        logger.info("Transcription complete for %s: %d chars", phase_id, len(transcript))
        preview = transcript[:500] + ("..." if len(transcript) > 500 else "")
        return TranscribeResult(
            phase_id=phase_id,
            char_count=len(transcript),
            transcript_preview=preview,
        )

    def extract_phase(self, session_name: str, phase_id: str) -> ExtractionResult:
        """Extract structured data from a phase transcript.

        Raises:
            FileNotFoundError: If session not found.
            ValueError: If phase not found, no transcript, or no extraction fields.
        """
        ensure_dirs()
        s = Session.load(session_name)
        tmpl = s.get_template()

        pt = next((p for p in tmpl.phases if p.id == phase_id), None)
        if not pt:
            raise ValueError(f"Phase '{phase_id}' not found")

        ps = s.phases[phase_id]
        transcript = s.get_transcript(phase_id)
        if not transcript:
            raise ValueError(f"No transcript for phase '{phase_id}'")

        if not pt.extract:
            # No extraction fields - mark complete
            ps.status = "complete"
            s.save()
            return ExtractionResult(
                phase_id=phase_id,
                phase_name=pt.name,
                fields={},
                field_count=0,
            )

        # Gather context from previous phases
        context = self._gather_context(s, tmpl, phase_id)

        # Run extraction
        extraction_fields = [
            {"id": e.id, "type": e.type, "prompt": e.prompt}
            for e in pt.extract
        ]

        from sift.engine import extract_structured_data
        extracted = extract_structured_data(
            transcript=transcript,
            extraction_fields=extraction_fields,
            phase_name=pt.name,
            context=context,
        )

        # Save extracted data
        dest = s.phase_dir(phase_id) / "extracted.yaml"
        with open(dest, "w") as f:
            yaml.dump(
                extracted, f,
                default_flow_style=False,
                sort_keys=False,
                allow_unicode=True,
            )

        ps.extracted_file = dest.name
        ps.status = "extracted"
        ps.extracted_at = datetime.now().isoformat()
        s.save()

        field_count = sum(1 for k in extracted if not k.startswith("_"))
        logger.info("Extraction complete for %s: %d fields", phase_id, field_count)

        return ExtractionResult(
            phase_id=phase_id,
            phase_name=pt.name,
            fields=extracted,
            field_count=field_count,
        )

    def get_remaining_phases(self, session_name: str) -> list[dict]:
        """Get remaining incomplete phases with suggested next action."""
        s = Session.load(session_name)
        tmpl = s.get_template()
        remaining = []
        for pt in tmpl.phases:
            ps = s.phases.get(pt.id)
            if ps and ps.status not in ("extracted", "complete"):
                remaining.append({
                    "phase_id": pt.id,
                    "phase_name": pt.name,
                    "status": ps.status,
                })
        return remaining

    def _capture_pdf(
        self, s: Session, pt, ps, phase_dir: Path, file_path: Path, now: str
    ) -> CaptureResult:
        """Handle PDF capture with text extraction."""
        from sift.pdf import extract_text_from_pdf, PDF_AVAILABLE

        if not PDF_AVAILABLE:
            raise ImportError(
                "PDF support not available. Install with: pip install pdfplumber"
            )

        pdf_text, pdf_stats = extract_text_from_pdf(file_path)

        # Save original PDF
        pdf_dest = phase_dir / "document.pdf"
        shutil.copy2(file_path, pdf_dest)

        # Save extracted text as transcript
        transcript_dest = phase_dir / "transcript.txt"
        transcript_dest.write_text(pdf_text)

        ps.transcript_file = transcript_dest.name
        ps.status = "transcribed"
        ps.captured_at = now
        ps.transcribed_at = now
        s.save()

        # Check if multi-phase
        from sift.document_analyzer import detect_multi_phase_content
        tmpl = s.get_template()
        multi = (
            len(tmpl.phases) > 1
            and detect_multi_phase_content(pdf_text, tmpl.phases)
        )

        logger.info(
            "PDF captured for %s: %d pages, %d chars",
            ps.id, pdf_stats["page_count"], pdf_stats["char_count"],
        )

        return CaptureResult(
            phase_id=ps.id,
            phase_name=pt.name,
            status="transcribed",
            file_type="pdf",
            char_count=pdf_stats["char_count"],
            pdf_stats=pdf_stats,
            multi_phase_detected=multi,
        )

    def _gather_context(
        self, s: Session, tmpl, current_phase_id: str
    ) -> str:
        """Gather context from previous phases for extraction."""
        context_parts = []
        for prev_pt in tmpl.phases:
            if prev_pt.id == current_phase_id:
                break
            prev_data = s.get_extracted(prev_pt.id)
            if prev_data:
                context_parts.append(
                    f"Data from '{prev_pt.name}':\n"
                    f"{yaml.dump(prev_data, default_flow_style=False)}"
                )
        return "\n\n".join(context_parts) if context_parts else ""
