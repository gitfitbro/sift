"""Google Gemini AI provider."""
from __future__ import annotations
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger("sift.providers.gemini")

# Available Gemini models for easy reference
GEMINI_MODELS = {
    # Flash models (fast, cost-effective)
    "gemini-2.0-flash": "Fast, versatile (default)",
    "gemini-2.0-flash-lite": "Fastest, lowest cost",
    "gemini-1.5-flash": "Previous gen fast model",
    "gemini-1.5-flash-8b": "Smallest, cheapest model",
    # Pro models (highest capability)
    "gemini-2.5-pro-preview-05-06": "Most capable, thinking model",
    "gemini-2.0-pro": "High capability, balanced",
    "gemini-1.5-pro": "Previous gen pro model",
}


def _import_genai():
    """Import google.genai with helpful error on failure."""
    try:
        import google.genai as genai
        return genai
    except ImportError:
        raise ImportError(
            "Cannot import google.genai. Install with:\n"
            "  pip install google-genai\n\n"
            "If you have the deprecated 'google-generativeai' package,\n"
            "uninstall it first to avoid conflicts:\n"
            "  pip uninstall google-generativeai && pip install google-genai"
        )


class GeminiProvider:
    name = "gemini"

    def __init__(self):
        from sift.core.secrets import get_key
        from sift.core.config_service import get_config_service

        self.api_key = get_key("gemini")
        self.model = get_config_service().get_provider_model("gemini")

    def is_available(self) -> bool:
        return self.api_key is not None

    def chat(self, system: str, user: str, max_tokens: int = 4000) -> str:
        """Send a chat message and return the response text."""
        genai = _import_genai()
        from google.genai import types

        client = genai.Client(api_key=self.api_key)

        config = types.GenerateContentConfig(max_output_tokens=max_tokens)
        if system:
            config.system_instruction = system

        try:
            response = client.models.generate_content(
                model=self.model,
                contents=user,
                config=config,
            )
            return response.text
        except Exception as e:
            from sift.errors import (
                ProviderAuthError, ProviderQuotaError,
                ProviderModelError, ProviderError,
            )
            err_msg = str(e).lower()
            if "quota" in err_msg or "resource_exhausted" in err_msg or "429" in err_msg:
                raise ProviderQuotaError(
                    "Gemini quota exceeded.\n"
                    "Free tier limit reached. Check billing at "
                    "https://ai.google.dev/gemini-api/docs/rate-limits",
                    provider=self.name, model=self.model,
                ) from e
            if "invalid" in err_msg and "key" in err_msg:
                raise ProviderAuthError(
                    "Gemini API key invalid.\n"
                    "Check that GOOGLE_API_KEY is valid and the "
                    "Generative Language API is enabled.",
                    provider=self.name, model=self.model,
                ) from e
            if "not found" in err_msg or "does not exist" in err_msg:
                available = "\n".join(f"  {m} - {d}" for m, d in GEMINI_MODELS.items())
                raise ProviderModelError(
                    f"Model '{self.model}' not found.\n"
                    f"Available models:\n{available}\n\n"
                    "Set via: GEMINI_MODEL=model-name or --model flag",
                    provider=self.name, model=self.model,
                ) from e
            raise ProviderError(
                f"Gemini API error: {e}",
                provider=self.name, model=self.model,
            ) from e

    def transcribe(self, audio_path: Path) -> Optional[str]:
        """Transcribe audio using Gemini's file upload API."""
        try:
            genai = _import_genai()

            client = genai.Client(api_key=self.api_key)
            logger.info("Transcribing with Gemini (%s)...", self.model)

            audio_file = client.files.upload(file=audio_path)
            response = client.models.generate_content(
                model=self.model,
                contents=[
                    audio_file,
                    "Please transcribe this audio recording verbatim. "
                    "Include all speakers, filler words, and natural speech patterns. "
                    "If there are multiple speakers, label them (Speaker 1, Speaker 2, etc). "
                    "Output ONLY the transcript text, nothing else.",
                ],
            )
            return response.text
        except ImportError as e:
            logger.error("Gemini import error: %s", e)
            return None
        except Exception as e:
            from sift.errors import ProviderError
            raise ProviderError(
                f"Gemini transcription failed: {e}",
                provider=self.name, model=self.model,
            ) from e
