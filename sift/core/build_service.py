"""Build service - business logic for generating outputs from sessions."""
from __future__ import annotations

import logging
import yaml
from pathlib import Path

from sift.core import BuildResult
from sift.models import ensure_dirs, Session

logger = logging.getLogger("sift.core.build")


class BuildService:
    """Generates outputs from completed session data."""

    def generate_outputs(
        self, session_name: str, format: str = "all"
    ) -> BuildResult:
        """Generate outputs from a session's extracted data.

        Args:
            session_name: Name of the session.
            format: Output format - "yaml", "markdown", or "all".

        Returns:
            BuildResult with list of generated files.

        Raises:
            FileNotFoundError: If session not found.
            ValueError: If no extracted data found.
        """
        ensure_dirs()
        s = Session.load(session_name)
        tmpl = s.get_template()
        output_dir = s.dir / "outputs"
        output_dir.mkdir(exist_ok=True)

        # Collect all extracted data
        all_data = {}
        all_transcripts = {}

        for pt in tmpl.phases:
            extracted = s.get_extracted(pt.id)
            if extracted:
                all_data[pt.id] = extracted
            transcript = s.get_transcript(pt.id)
            if transcript:
                all_transcripts[pt.id] = transcript

        if not all_data:
            from sift.errors import ExtractionError
            raise ExtractionError(
                "No extracted data found. Run extraction first.",
                session_name=session_name,
            )

        generated = []

        if format in ("yaml", "all"):
            config = self._build_yaml_config(s, tmpl, all_data)
            config_path = output_dir / "session-config.yaml"
            with open(config_path, "w") as f:
                yaml.dump(
                    config, f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
            generated.append(("YAML Config", config_path))

        if format in ("markdown", "all"):
            md = self._build_markdown(s, tmpl, all_data, all_transcripts)
            md_path = output_dir / "session-summary.md"
            md_path.write_text(md)
            generated.append(("Markdown Summary", md_path))

        if format in ("yaml", "all"):
            consolidated = self._build_consolidated(s, tmpl, all_data)
            con_path = output_dir / "extracted-data.yaml"
            with open(con_path, "w") as f:
                yaml.dump(
                    consolidated, f,
                    default_flow_style=False,
                    sort_keys=False,
                    allow_unicode=True,
                )
            generated.append(("Consolidated Data", con_path))

        logger.info(
            "Generated %d outputs for session '%s'",
            len(generated), session_name,
        )

        return BuildResult(generated_files=generated, output_dir=output_dir)

    def generate_summary(self, session_name: str) -> tuple[str, Path]:
        """Generate an AI-powered narrative summary.

        Returns:
            Tuple of (summary_text, saved_path).

        Raises:
            FileNotFoundError: If session not found.
            ValueError: If no data to summarize.
        """
        ensure_dirs()
        s = Session.load(session_name)
        tmpl = s.get_template()

        session_data = {}
        for pt in tmpl.phases:
            phase_bundle = {}
            transcript = s.get_transcript(pt.id)
            if transcript:
                phase_bundle["transcript_preview"] = transcript[:2000]
            extracted = s.get_extracted(pt.id)
            if extracted:
                phase_bundle["extracted"] = extracted
            if phase_bundle:
                session_data[pt.name] = phase_bundle

        if not session_data:
            from sift.errors import ExtractionError
            raise ExtractionError(
                "No data to summarize.",
                session_name=session_name,
            )

        from sift.engine import generate_summary
        summary = generate_summary(session_data, tmpl.name)

        output_dir = s.dir / "outputs"
        output_dir.mkdir(exist_ok=True)
        summary_path = output_dir / "ai-summary.md"
        summary_path.write_text(summary)

        logger.info("AI summary generated for session '%s'", session_name)
        return summary, summary_path

    def _build_yaml_config(self, s: Session, tmpl, all_data: dict) -> dict:
        """Build the session configuration YAML."""
        config = {
            "session": {
                "name": s.name,
                "template": s.template_name,
                "created": s.created_at,
                "status": s.status,
            },
            "phases_completed": [],
            "data": {},
        }

        for pt in tmpl.phases:
            ps = s.phases.get(pt.id)
            if ps and ps.status in ("extracted", "complete"):
                config["phases_completed"].append({
                    "id": pt.id,
                    "name": pt.name,
                    "captured_at": ps.captured_at,
                    "extracted_at": ps.extracted_at,
                })
            if pt.id in all_data:
                config["data"][pt.id] = all_data[pt.id]

        return config

    def _build_markdown(
        self, s: Session, tmpl, all_data: dict, all_transcripts: dict
    ) -> str:
        """Build a markdown summary document."""
        lines = [
            f"# {tmpl.name}: Session Summary",
            "",
            f"**Session:** {s.name}  ",
            f"**Template:** {s.template_name}  ",
            f"**Created:** {s.created_at[:16]}  ",
            f"**Status:** {s.status}",
            "",
            "---",
            "",
        ]

        for pt in tmpl.phases:
            ps = s.phases.get(pt.id)
            if not ps or ps.status == "pending":
                continue

            lines.append(f"## {pt.name}")
            lines.append("")

            extracted = all_data.get(pt.id, {})
            if extracted:
                for field_id, value in extracted.items():
                    if field_id.startswith("_"):
                        continue

                    lines.append(f"### {field_id.replace('_', ' ').title()}")
                    lines.append("")

                    if isinstance(value, list):
                        for item in value:
                            if isinstance(item, dict):
                                for k, v in item.items():
                                    lines.append(f"- **{k}**: {v}")
                            else:
                                lines.append(f"- {item}")
                    elif isinstance(value, dict):
                        for k, v in value.items():
                            lines.append(f"- **{k}**: {v}")
                    else:
                        lines.append(str(value))

                    lines.append("")

            lines.append("---")
            lines.append("")

        if all_transcripts:
            lines.append("## Raw Transcripts")
            lines.append("")
            for phase_id, transcript in all_transcripts.items():
                pt = next((p for p in tmpl.phases if p.id == phase_id), None)
                name = pt.name if pt else phase_id
                lines.append(f"### {name}")
                lines.append("")
                lines.append("```")
                lines.append(transcript[:3000])
                if len(transcript) > 3000:
                    lines.append(
                        f"\n... [truncated, {len(transcript)} total chars]"
                    )
                lines.append("```")
                lines.append("")

        return "\n".join(lines)

    def _build_consolidated(self, s: Session, tmpl, all_data: dict) -> dict:
        """Build a flat consolidated view of all extracted data."""
        consolidated = {
            "meta": {
                "session": s.name,
                "template": s.template_name,
                "generated_at": s.updated_at,
            }
        }

        for phase_id, data in all_data.items():
            if isinstance(data, dict):
                for k, v in data.items():
                    if not k.startswith("_"):
                        consolidated[k] = v

        return consolidated
