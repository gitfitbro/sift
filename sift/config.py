"""Configuration and environment variable handling for sift.

This module delegates to sift.core.config_service for layered config resolution
and sift.core.secrets for API key management. It maintains backward-compatible
exports used by existing code.
"""
import os
from pathlib import Path
from typing import Optional

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    pass


# Map provider names to their env var for API keys (kept for backward compat)
PROVIDER_KEY_MAP = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
    "ollama": None,
}


class Config:
    """Central configuration for sift.

    Delegates to ConfigService for layered resolution and secrets module
    for API key management.
    """

    @staticmethod
    def get_ai_provider() -> str:
        """Get the active AI provider name."""
        from sift.core.config_service import get_config_service
        return get_config_service().get_provider_name()

    @staticmethod
    def get_anthropic_api_key() -> Optional[str]:
        """Get Anthropic API key."""
        from sift.core.secrets import get_key
        return get_key("anthropic")

    @staticmethod
    def get_google_api_key() -> Optional[str]:
        """Get Google/Gemini API key."""
        from sift.core.secrets import get_key
        return get_key("gemini")

    @staticmethod
    def get_provider_api_key(provider: str = None) -> Optional[str]:
        """Get the API key for the specified or current provider."""
        from sift.core.secrets import get_key
        provider = provider or Config.get_ai_provider()
        return get_key(provider)

    @staticmethod
    def get_sift_home() -> Path:
        """Get the base directory for all sift data."""
        from sift.core.config_service import get_config_service
        return get_config_service().get_data_dir()

    @staticmethod
    def require_api_key() -> str:
        """Get API key for the current provider, or raise with a helpful error."""
        provider = Config.get_ai_provider()
        key = Config.get_provider_api_key(provider)
        if not key:
            env_var = PROVIDER_KEY_MAP.get(provider, f"{provider.upper()}_API_KEY")
            raise ValueError(
                f"Provider '{provider}' requires {env_var} to be set.\n"
                f"  export {env_var}=your-key-here\n\n"
                "Or store it securely:\n"
                f"  sift config set-key {provider} your-key-here\n\n"
                "Or create a .env file in the project directory:\n"
                "  cp .env.example .env\n"
                "  # Edit .env and add your key"
            )
        return key

    @staticmethod
    def check_setup() -> dict:
        """Check if environment is properly configured."""
        provider = Config.get_ai_provider()
        return {
            "ai_provider": provider,
            "api_key_set": Config.get_provider_api_key(provider) is not None,
            "anthropic_key_set": Config.get_anthropic_api_key() is not None,
            "google_key_set": Config.get_google_api_key() is not None,
            "sift_home": Config.get_sift_home(),
            "sift_home_exists": Config.get_sift_home().exists(),
        }


# Convenience exports
get_api_key = Config.get_provider_api_key
require_api_key = Config.require_api_key
get_sift_home = Config.get_sift_home
