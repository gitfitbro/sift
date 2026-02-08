"""Telemetry consent management - opt-in only, GDPR/CCPA compliant."""

import os
import logging
from pathlib import Path

logger = logging.getLogger("sift.telemetry.consent")

# What we collect (shown to users during opt-in prompt)
COLLECTED = [
    "Command names (e.g. 'new', 'extract', 'build')",
    "Command durations (how long commands take)",
    "Error types (e.g. 'FileNotFoundError', never stack traces)",
    "Python version and OS type (e.g. 'Python 3.12, macOS')",
    "AI provider and model names used",
]

# What we NEVER collect
NEVER_COLLECTED = [
    "File paths or file contents",
    "Environment variables or API keys",
    "Session data, transcripts, or extracted content",
    "Hostnames, IP addresses, or usernames",
    "Git information or repository data",
    "Stack traces or detailed error messages",
]


class ConsentManager:
    """Manages telemetry opt-in/opt-out consent."""

    def __init__(self, config_dir: Path | None = None):
        self._config_dir = config_dir or Path.home() / ".config" / "sift"
        self._consent_file = self._config_dir / ".telemetry-consent"

    @property
    def consent_file(self) -> Path:
        return self._consent_file

    def is_enabled(self) -> bool:
        """Check if telemetry is enabled.

        Priority:
        1. SIFT_TELEMETRY env var (highest)
        2. Consent file on disk
        3. Default: disabled
        """
        env_val = os.environ.get("SIFT_TELEMETRY", "").lower()
        if env_val in ("1", "true", "enabled", "on"):
            return True
        if env_val in ("0", "false", "disabled", "off"):
            return False

        if self._consent_file.exists():
            try:
                content = self._consent_file.read_text().strip().lower()
                return content == "enabled"
            except OSError:
                logger.debug("Failed to read consent file")
                return False

        return False

    def enable(self) -> None:
        """Opt in to telemetry."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._consent_file.write_text("enabled\n")
        logger.info("Telemetry enabled")

    def disable(self) -> None:
        """Opt out of telemetry."""
        self._config_dir.mkdir(parents=True, exist_ok=True)
        self._consent_file.write_text("disabled\n")
        logger.info("Telemetry disabled")

    def status(self) -> dict:
        """Get current telemetry status with details."""
        env_val = os.environ.get("SIFT_TELEMETRY", "")
        source = "default"
        if env_val:
            source = "environment"
        elif self._consent_file.exists():
            source = "consent_file"

        return {
            "enabled": self.is_enabled(),
            "source": source,
            "consent_file": str(self._consent_file),
            "env_override": env_val or None,
            "collected": COLLECTED,
            "never_collected": NEVER_COLLECTED,
        }
