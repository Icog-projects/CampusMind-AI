"""CampusMind AI - Large Language Model Service.

Provides extensible provider abstraction for text generation, supporting Groq LLM integration.

Responsibilities:
Class BaseLLMProvider:
1. BaseLLMProvider.generate(): Abstract interface defining the generation contract.
Class GroqProvider:
2. GroqProvider.__init__(): Initializes the Groq client, API key, model, and timeout settings.
3. GroqProvider.generate(): Sends chat completion requests to the Groq API and handles provider errors.
"""

import os
import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any

from dotenv import load_dotenv

load_dotenv()
logger = logging.getLogger(__name__)

DEFAULT_GROQ_MODEL = "openai/gpt-oss-120b"


class LLMError(Exception):
    """Base exception for LLM provider errors."""
    pass


class LLMConfigurationError(LLMError):
    """Raised when LLM configuration (such as API keys) is missing or invalid."""
    pass


class LLMTimeoutError(LLMError):
    """Raised when an LLM API request times out."""
    pass


class LLMAPIError(LLMError):
    """Raised when an LLM API returns an error response."""
    pass


class BaseLLMProvider(ABC):
    """Abstract interface defining the contract for LLM providers."""

    @abstractmethod
    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Executes a completion/chat request.

        Returns a dictionary with:
            - "content": str
            - "model": str
            - "prompt_tokens": Optional[int]
            - "completion_tokens": Optional[int]
        """
        pass


class GroqProvider(BaseLLMProvider):
    """
    Groq LLM provider implementation using the official `groq` SDK.
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: float = 30.0,
        client: Optional[Any] = None,
    ):
        """
        Initializes the Groq provider.

        Args:
            api_key: Optional Groq API key (defaults to GROQ_API_KEY environment variable).
            model: Optional model identifier (defaults to GROQ_MODEL or openai/gpt-oss-120b).
            timeout: Request timeout in seconds.
            client: Optional pre-configured Groq client (useful for dependency injection / mocking).
        """
        if api_key is not None:
            self.api_key = api_key
        else:
            self.api_key = os.getenv("GROQ_API_KEY")

        self.model = model or os.getenv("GROQ_MODEL", DEFAULT_GROQ_MODEL)
        self.timeout = timeout

        if client is not None:
            self._client = client
        else:
            if not self.api_key or self.api_key.strip() in ("", "your_groq_api_key_here"):
                raise LLMConfigurationError(
                    "GROQ_API_KEY is not configured or contains placeholder values. "
                    "Please set a valid GROQ_API_KEY in backend/.env."
                )

            try:
                from groq import Groq
                self._client = Groq(api_key=self.api_key, timeout=self.timeout)
            except ImportError:
                raise LLMConfigurationError(
                    "The 'groq' package is not installed. Please install it with 'pip install groq'."
                )
            except Exception as e:
                raise LLMConfigurationError(f"Failed to initialize Groq client: {e}")

    def generate(
        self,
        messages: List[Dict[str, str]],
        temperature: float = 0.1,
        max_tokens: int = 1024,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Sends chat completion messages to Groq.
        """
        if not messages:
            raise ValueError("Messages list cannot be empty.")

        try:
            import groq

            response = self._client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=temperature,
                max_tokens=max_tokens,
                **kwargs,
            )

            choice = response.choices[0]
            content = choice.message.content or ""

            prompt_tokens = getattr(response.usage, "prompt_tokens", None) if hasattr(response, "usage") else None
            completion_tokens = getattr(response.usage, "completion_tokens", None) if hasattr(response, "usage") else None

            return {
                "content": content,
                "model": response.model or self.model,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": completion_tokens,
            }

        except Exception as e:
            # Map known Groq / HTTP errors
            err_type = type(e).__name__
            err_msg = str(e)

            if "timeout" in err_type.lower() or "timeout" in err_msg.lower():
                logger.error("Groq API request timed out: %s", err_msg)
                raise LLMTimeoutError(f"Groq request timed out: {err_msg}") from e

            if "auth" in err_type.lower() or "authentication" in err_msg.lower():
                logger.error("Groq authentication failed: %s", err_msg)
                raise LLMConfigurationError(f"Groq authentication failed: {err_msg}") from e

            logger.error("Groq API error (%s): %s", err_type, err_msg)
            raise LLMAPIError(f"Groq API error: {err_msg}") from e
