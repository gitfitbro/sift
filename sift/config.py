"""Configuration and environment variable handling for sift."""
import os
from pathlib import Path
from typing import Optional

# Try to load .env file if it exists
try:
    from dotenv import load_dotenv
    # Look for .env in project directory
    project_root = Path(__file__).parent.parent
    env_file = project_root / ".env"
    if env_file.exists():
        load_dotenv(env_file)
except ImportError:
    # python-dotenv not installed, that's okay - use system env vars
    pass


# Map provider names to their env var for API keys
PROVIDER_KEY_MAP = {
    "anthropic": "ANTHROPIC_API_KEY",
    "gemini": "GOOGLE_API_KEY",
}


class Config:
    """Central configuration for sift."""

    @staticmethod
    def get_ai_provider() -> str:
        """Get the active AI provider name. Default: anthropic."""
        return os.environ.get("AI_PROVIDER", "anthropic")

    @staticmethod
    def get_anthropic_api_key() -> Optional[str]:
        """Get Anthropic API key from environment."""
        return os.environ.get("ANTHROPIC_API_KEY")

    @staticmethod
    def get_google_api_key() -> Optional[str]:
        """Get Google/Gemini API key from environment."""
        return os.environ.get("GOOGLE_API_KEY")

    @staticmethod
    def get_provider_api_key(provider: str = None) -> Optional[str]:
        """Get the API key for the specified or current provider."""
        provider = provider or Config.get_ai_provider()
        env_var = PROVIDER_KEY_MAP.get(provider)
        return os.environ.get(env_var) if env_var else None

    @staticmethod
    def get_sift_home() -> Path:
        """Get the base directory for all sift data.

        Priority:
        1. SIFT_HOME environment variable (if set)
        2. Project-local directory (./data/)
        3. Global home directory (~/.sift) - legacy fallback
        """
        # Check for explicit SIFT_HOME override
        env_home = os.environ.get("SIFT_HOME")
        if env_home:
            return Path(env_home).expanduser()

        # Default to project-local data directory
        project_root = Path(__file__).parent.parent
        project_data = project_root / "data"

        # For backwards compatibility: if ~/.sift exists and project data doesn't, use ~/.sift
        global_home = Path.home() / ".sift"
        if global_home.exists() and not project_data.exists():
            return global_home

        # Otherwise use project-local (create if needed)
        return project_data

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
