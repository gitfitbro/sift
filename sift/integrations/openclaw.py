"""OpenClaw/Clawd.bot integration for sift.

Exposes sift as conversational commands for messaging platforms
(Slack, Discord, Telegram) via the Clawd.bot skill interface.
"""

from __future__ import annotations

import logging

logger = logging.getLogger("sift.integrations.openclaw")


class SiftClawdSkill:
    """Sift skill for Clawd.bot / OpenClaw messaging integration.

    Manages active sessions per channel and dispatches slash commands.
    """

    def __init__(self):
        self._active_sessions: dict[str, str] = {}  # channel_id -> session_name

    @staticmethod
    def get_commands() -> list[dict]:
        """Return command definitions for Clawd.bot registration."""
        return [
            {
                "command": "/sift new",
                "description": "Create a new sift session",
                "usage": "/sift new <template> [name]",
            },
            {
                "command": "/sift capture",
                "description": "Capture text for the current phase",
                "usage": "/sift capture <phase_id> <text>",
            },
            {
                "command": "/sift next",
                "description": "Show next suggested action",
                "usage": "/sift next",
            },
            {
                "command": "/sift extract",
                "description": "Extract structured data from a phase",
                "usage": "/sift extract <phase_id>",
            },
            {
                "command": "/sift status",
                "description": "Show session status",
                "usage": "/sift status",
            },
            {
                "command": "/sift done",
                "description": "Build outputs and finish session",
                "usage": "/sift done",
            },
        ]

    def handle_message(
        self,
        channel_id: str,
        text: str,
        user_id: str | None = None,
    ) -> str:
        """Dispatch a /sift command and return a text response.

        Args:
            channel_id: The messaging channel/room ID.
            text: The full command text (e.g. "/sift new discovery-call").
            user_id: Optional user identifier.

        Returns:
            Formatted text response for the messaging platform.
        """
        parts = text.strip().split(None, 2)  # "/sift", subcommand, rest

        if len(parts) < 2:
            return self._help()

        subcommand = parts[1].lower()
        args = parts[2] if len(parts) > 2 else ""

        dispatch = {
            "new": self._cmd_new,
            "capture": self._cmd_capture,
            "next": self._cmd_next,
            "extract": self._cmd_extract,
            "status": self._cmd_status,
            "done": self._cmd_done,
            "help": lambda _cid, _args: self._help(),
        }

        handler = dispatch.get(subcommand)
        if not handler:
            return f"Unknown command: {subcommand}\n{self._help()}"

        try:
            return handler(channel_id, args)
        except Exception as e:
            logger.error("Command failed: %s", e, exc_info=True)
            return f"Error: {e}"

    def _cmd_new(self, channel_id: str, args: str) -> str:
        from sift.core.session_service import SessionService

        parts = args.strip().split(None, 1)
        if not parts:
            return "Usage: /sift new <template> [name]"

        template = parts[0]
        name = parts[1] if len(parts) > 1 else None

        svc = SessionService()
        detail = svc.create_session(template, name)
        self._active_sessions[channel_id] = detail.name

        phases = ", ".join(p.id for p in detail.phases)
        return (
            f"Session created: {detail.name}\n"
            f"Template: {detail.template_name}\n"
            f"Phases ({detail.total_phases}): {phases}\n"
            f"Next: capture content for '{detail.next_action_phase}'"
        )

    def _cmd_capture(self, channel_id: str, args: str) -> str:
        from sift.core.extraction_service import ExtractionService

        session_name = self._get_active(channel_id)
        if not session_name:
            return "No active session. Use /sift new <template> first."

        parts = args.strip().split(None, 1)
        if len(parts) < 2:
            return "Usage: /sift capture <phase_id> <text>"

        phase_id, text = parts[0], parts[1]
        svc = ExtractionService()
        result = svc.capture_text(session_name, phase_id, text)
        return (
            f"Captured {result.char_count} chars for '{result.phase_name}'\nStatus: {result.status}"
        )

    def _cmd_next(self, channel_id: str, args: str) -> str:
        from sift.core.session_service import SessionService

        session_name = self._get_active(channel_id)
        if not session_name:
            return "No active session. Use /sift new <template> first."

        svc = SessionService()
        detail = svc.get_session_status(session_name)

        if not detail.next_action:
            return f"Session '{detail.name}' is complete. Use /sift done to build outputs."

        return (
            f"Session: {detail.name} ({detail.done_phases}/{detail.total_phases} phases done)\n"
            f"Next action: {detail.next_action} phase '{detail.next_action_phase}'"
        )

    def _cmd_extract(self, channel_id: str, args: str) -> str:
        from sift.core.extraction_service import ExtractionService

        session_name = self._get_active(channel_id)
        if not session_name:
            return "No active session. Use /sift new <template> first."

        phase_id = args.strip()
        if not phase_id:
            return "Usage: /sift extract <phase_id>"

        svc = ExtractionService()
        result = svc.extract_phase(session_name, phase_id)
        fields = ", ".join(result.fields.keys()) if result.fields else "(none)"
        return f"Extracted {result.field_count} fields from '{result.phase_name}'\nFields: {fields}"

    def _cmd_status(self, channel_id: str, args: str) -> str:
        from sift.core.session_service import SessionService

        session_name = self._get_active(channel_id)
        if not session_name:
            return "No active session. Use /sift new <template> first."

        svc = SessionService()
        detail = svc.get_session_status(session_name)

        lines = [
            f"Session: {detail.name}",
            f"Template: {detail.template_name}",
            f"Progress: {detail.done_phases}/{detail.total_phases} phases",
            "",
        ]
        for p in detail.phases:
            icon = {
                "pending": "[ ]",
                "captured": "[~]",
                "transcribed": "[~]",
                "extracted": "[x]",
                "complete": "[x]",
            }.get(p.status, "[ ]")
            lines.append(f"  {icon} {p.id}: {p.status}")

        if detail.next_action:
            lines.append(f"\nNext: {detail.next_action} '{detail.next_action_phase}'")

        return "\n".join(lines)

    def _cmd_done(self, channel_id: str, args: str) -> str:
        from sift.core.build_service import BuildService

        session_name = self._get_active(channel_id)
        if not session_name:
            return "No active session. Use /sift new <template> first."

        svc = BuildService()
        result = svc.generate_outputs(session_name)
        files = "\n".join(f"  - {label}: {path}" for label, path in result.generated_files)

        del self._active_sessions[channel_id]
        return f"Outputs generated:\n{files}\n\nSession complete."

    def _get_active(self, channel_id: str) -> str | None:
        return self._active_sessions.get(channel_id)

    @staticmethod
    def _help() -> str:
        return (
            "Sift commands:\n"
            "  /sift new <template> [name] - Create session\n"
            "  /sift capture <phase> <text> - Capture text\n"
            "  /sift next - Show next action\n"
            "  /sift extract <phase> - Extract data\n"
            "  /sift status - Show progress\n"
            "  /sift done - Build outputs"
        )
