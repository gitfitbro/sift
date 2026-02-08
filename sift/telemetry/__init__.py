"""Telemetry subsystem for sift - opt-in only, privacy-first."""

from sift.telemetry.consent import ConsentManager
from sift.telemetry.service import get_telemetry

__all__ = ["ConsentManager", "get_telemetry"]
