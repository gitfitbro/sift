"""Extraction service - business logic for capture, transcription, and extraction."""

from __future__ import annotations

import logging
import shutil
from datetime import datetime
from pathlib import Path

import yaml

from sift.core import CaptureResult, ExtractionResult, TranscribeResult
from sift.errors import CaptureError, ExtractionError, PhaseNotFoundError
from sift.models import Session, ensure_dirs

logger = logging.getLogger("sift.core.extraction")

# File type classifications
AUDIO_EXTENSIONS = {".mp3", ".wav", ".webm", ".m4a", ".ogg", ".flac", ".mp4", ".aac"}
TEXT_EXTENSIONS = {".txt", ".md", ".text"}
PDF_EXTENSIONS = {".pdf"}


class ExtractionService:
    """Handles capture, transcription, and structured data extraction."""

    def capture_file(
        self, session_name: str, phase_id: str, file_path: Path, append: bool = False
    ) -> CaptureResult:
        """Capture a file (audio, text, or PDF) for a session phase.

        Args:
            append: If True and a transcript already exists, append new content
                    instead of replacing it. Resets status to "transcribed" if
                    previously extracted.

        Raises:
            SessionNotFoundError: If session not found.
            PhaseNotFoundError: If phase not found.
            CaptureError: If file not found or unsupported file type.
        """
        ensure_dirs()
        s = Session.load(session_name)
        tmpl = s.get_template()

        pt = next((p for p in tmpl.phases if p.id == phase_id), None)
        if not pt:
            raise PhaseNotFoundError(
                phase_id,
                session_name,
                available=[p.id for p in tmpl.phases],
            )

        if not file_path.exists():
            raise CaptureError(
                f"File not found: {file_path}",
                phase_id=phase_id,
                file_path=str(file_path),
            )

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
            new_text = file_path.read_text()
            appended = append and dest.exists() and dest.read_text().strip()
            if appended:
                existing = dest.read_text()
                dest.write_text(existing + "\n\n---\n\n" + new_text)
            else:
                shutil.copy2(file_path, dest)
            ps.transcript_file = dest.name
            ps.status = "transcribed"
            ps.captured_at = ps.captured_at or now
            ps.transcribed_at = now
            s.save()
            char_count = len(dest.read_text())
            logger.info(
                "Text captured for %s: %d chars (appended=%s)", phase_id, char_count, appended
            )
            return CaptureResult(
                phase_id=phase_id,
                phase_name=pt.name,
                status="transcribed",
                file_type="text",
                char_count=char_count,
                appended=bool(appended),
            )

        elif suffix in PDF_EXTENSIONS:
            return self._capture_pdf(s, pt, ps, phase_dir, file_path, now, append=append)

        else:
            supported = AUDIO_EXTENSIONS | TEXT_EXTENSIONS | PDF_EXTENSIONS
            raise CaptureError(
                f"Unsupported file type: {suffix}. Supported: {', '.join(sorted(supported))}",
                phase_id=phase_id,
                file_path=str(file_path),
            )

    def capture_text(
        self, session_name: str, phase_id: str, text: str, append: bool = False
    ) -> CaptureResult:
        """Capture text content directly for a session phase.

        Args:
            append: If True and a transcript already exists, append new content
                    instead of replacing it. Resets status to "transcribed" if
                    previously extracted.

        Raises:
            SessionNotFoundError: If session not found.
            PhaseNotFoundError: If phase not found.
            CaptureError: If text is empty.
        """
        ensure_dirs()
        s = Session.load(session_name)
        tmpl = s.get_template()

        pt = next((p for p in tmpl.phases if p.id == phase_id), None)
        if not pt:
            raise PhaseNotFoundError(phase_id, session_name)

        if not text.strip():
            raise CaptureError("No text provided", phase_id=phase_id)

        ps = s.phases[phase_id]
        phase_dir = s.phase_dir(phase_id)
        now = datetime.now().isoformat()

        dest = phase_dir / "transcript.txt"
        appended = append and dest.exists() and dest.read_text().strip()
        if appended:
            existing = dest.read_text()
            dest.write_text(existing + "\n\n---\n\n" + text)
        else:
            dest.write_text(text)
        total_chars = len(dest.read_text())

        ps.transcript_file = dest.name
        ps.status = "transcribed"
        ps.captured_at = ps.captured_at or now
        ps.transcribed_at = now
        s.save()

        logger.info("Text captured for %s: %d chars (appended=%s)", phase_id, total_chars, appended)
        return CaptureResult(
            phase_id=phase_id,
            phase_name=pt.name,
            status="transcribed",
            file_type="text",
            char_count=total_chars,
            appended=bool(appended),
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
            SessionNotFoundError: If session not found.
            PhaseNotFoundError: If phase not found.
            CaptureError: If no audio file exists for the phase.
        """
        ensure_dirs()
        s = Session.load(session_name)

        ps = s.phases.get(phase_id)
        if not ps:
            raise PhaseNotFoundError(phase_id, session_name)
        if not ps.audio_file:
            raise CaptureError(
                f"No audio file for phase '{phase_id}'",
                phase_id=phase_id,
            )

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
            SessionNotFoundError: If session not found.
            PhaseNotFoundError: If phase not found.
            ExtractionError: If no transcript available.
        """
        ensure_dirs()
        s = Session.load(session_name)
        tmpl = s.get_template()

        pt = next((p for p in tmpl.phases if p.id == phase_id), None)
        if not pt:
            raise PhaseNotFoundError(phase_id, session_name)

        ps = s.phases[phase_id]
        transcript = s.get_transcript(phase_id)
        if not transcript:
            raise ExtractionError(
                f"No transcript for phase '{phase_id}'",
                phase_id=phase_id,
                session_name=session_name,
            )

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

        # Gather context from previous phases + project analysis
        context = self._gather_context(s, tmpl, phase_id)
        analysis_context = self._load_analysis_context(s)
        if analysis_context:
            context = self._inject_analysis_context(context, analysis_context)

        # Run extraction
        extraction_fields = [{"id": e.id, "type": e.type, "prompt": e.prompt} for e in pt.extract]

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
                extracted,
                f,
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
                remaining.append(
                    {
                        "phase_id": pt.id,
                        "phase_name": pt.name,
                        "status": ps.status,
                    }
                )
        return remaining

    def _capture_pdf(
        self, s: Session, pt, ps, phase_dir: Path, file_path: Path, now: str, append: bool = False
    ) -> CaptureResult:
        """Handle PDF capture with text extraction."""
        from sift.pdf import PDF_AVAILABLE, extract_text_from_pdf

        if not PDF_AVAILABLE:
            raise CaptureError(
                "PDF support not available. Install with: pip install pdfplumber",
                phase_id=ps.id,
            )

        pdf_text, pdf_stats = extract_text_from_pdf(file_path)

        # Save original PDF
        pdf_dest = phase_dir / "document.pdf"
        shutil.copy2(file_path, pdf_dest)

        # Save extracted text as transcript (append if requested)
        transcript_dest = phase_dir / "transcript.txt"
        appended = append and transcript_dest.exists() and transcript_dest.read_text().strip()
        if appended:
            existing = transcript_dest.read_text()
            transcript_dest.write_text(existing + "\n\n---\n\n" + pdf_text)
        else:
            transcript_dest.write_text(pdf_text)

        ps.transcript_file = transcript_dest.name
        ps.status = "transcribed"
        ps.captured_at = ps.captured_at or now
        ps.transcribed_at = now
        s.save()

        # Check if multi-phase
        from sift.document_analyzer import detect_multi_phase_content

        tmpl = s.get_template()
        multi = len(tmpl.phases) > 1 and detect_multi_phase_content(pdf_text, tmpl.phases)

        total_chars = len(transcript_dest.read_text())
        logger.info(
            "PDF captured for %s: %d pages, %d chars (appended=%s)",
            ps.id,
            pdf_stats["page_count"],
            total_chars,
            appended,
        )

        return CaptureResult(
            phase_id=ps.id,
            phase_name=pt.name,
            status="transcribed",
            file_type="pdf",
            char_count=total_chars,
            pdf_stats=pdf_stats,
            multi_phase_detected=multi,
            appended=bool(appended),
        )

    def _gather_context(self, s: Session, tmpl, current_phase_id: str) -> str:
        """Gather context from previous phases for extraction."""
        context_parts = []
        for prev_pt in tmpl.phases:
            if prev_pt.id == current_phase_id:
                break
            prev_data = s.get_extracted(prev_pt.id)
            if prev_data:
                context_parts.append(
                    f"Data from '{prev_pt.name}':\n{yaml.dump(prev_data, default_flow_style=False)}"
                )
        return "\n\n".join(context_parts) if context_parts else ""

    def _load_analysis_context(self, session: Session) -> dict | None:
        """Load stored project analysis context from the session directory."""
        analysis_path = session.dir / "analysis.yaml"
        if analysis_path.exists():
            with open(analysis_path) as f:
                return yaml.safe_load(f)
        return None

    def _inject_analysis_context(self, existing_context: str, analysis: dict) -> str:
        """Prepend project analysis summary to extraction context."""
        project_lines = [
            f"Project context ({analysis.get('project_name', 'unknown')}):",
        ]

        languages = analysis.get("languages", {})
        if languages:
            lang_str = ", ".join(f"{k} ({v} files)" for k, v in languages.items())
            project_lines.append(f"  Languages: {lang_str}")

        frameworks = analysis.get("frameworks")
        if frameworks:
            project_lines.append(f"  Frameworks: {', '.join(frameworks)}")

        entry_points = analysis.get("entry_points")
        if entry_points:
            project_lines.append(f"  Entry points: {', '.join(entry_points[:5])}")

        arch = analysis.get("architecture_summary")
        if arch:
            project_lines.append(f"  Architecture: {arch[:300]}")

        project_summary = "\n".join(project_lines)

        if existing_context:
            return f"{project_summary}\n\n{existing_context}"
        return project_summary
