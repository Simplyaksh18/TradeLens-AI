"""Phase 5B: LLM provider abstraction. `app.ai.service` depends on
`ResearchLanguageModel` only -- never on the Groq SDK directly -- so the
domain layer stays swappable and independently testable with a fake
provider (see tests/unit/ai/)."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.ai.models import LanguageModelRequest, LanguageModelResponse
from app.core.config import settings
from app.core.exceptions import MissingProviderConfigurationError, ProviderRequestFailedError


class ResearchLanguageModel(ABC):
    """Conceptual interface every LLM backend implements."""

    @abstractmethod
    def generate(self, request: LanguageModelRequest) -> LanguageModelResponse: ...

    @property
    def model_name(self) -> str | None:
        """Optional provider/model metadata for the response (never a raw
        SDK object) -- `None` when a provider has no single model name."""
        return None


class GroqResearchLanguageModel(ResearchLanguageModel):
    """Groq-backed `ResearchLanguageModel`. The Groq SDK client is
    constructed lazily on first `generate()` call (never at import time
    or `__init__`), so importing/instantiating this class never requires
    `GROQ_API_KEY` to be set -- only actually generating a response does.
    Raw Groq SDK exceptions/response objects never leave this class."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        self._api_key = api_key if api_key is not None else settings.groq_api_key
        self._model = model if model is not None else settings.groq_model
        self._client = None

    @property
    def model_name(self) -> str | None:
        return self._model

    def generate(self, request: LanguageModelRequest) -> LanguageModelResponse:
        if not self._api_key:
            raise MissingProviderConfigurationError(
                "GROQ_API_KEY is not configured. Set it in backend/.env "
                "(server-side only -- see backend/.env.example) before "
                "invoking the Groq research language model."
            )

        client = self._get_client()

        try:
            completion = client.chat.completions.create(
                model=self._model,
                messages=[
                    {"role": "system", "content": request.system_instruction},
                    {"role": "user", "content": request.user_prompt},
                ],
            )
        except Exception as exc:  # narrow re-raise; never leak the SDK exception type
            raise ProviderRequestFailedError(f"Groq request failed: {exc}") from exc

        text = completion.choices[0].message.content if completion.choices else ""
        return LanguageModelResponse(text=(text or "").strip())

    def _get_client(self):
        if self._client is None:
            from groq import Groq  # imported lazily so the SDK is only touched when actually used

            self._client = Groq(api_key=self._api_key)
        return self._client
