"""Phase 5B: GroqResearchLanguageModel adapter tests. The Groq SDK is
always mocked -- no test in this file makes a real network call or
requires a real API key."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.ai.models import LanguageModelRequest
from app.ai.provider import GroqResearchLanguageModel
from app.core.exceptions import MissingProviderConfigurationError, ProviderRequestFailedError


def _request() -> LanguageModelRequest:
    return LanguageModelRequest(system_instruction="system", user_prompt="user")


def test_missing_api_key_raises_controlled_error():
    # Explicitly "" (falsy), never None -- None would fall back to
    # `settings.groq_api_key`, which may be genuinely configured in this
    # environment (e.g. a real key set for the manual verification
    # script). This test must be isolated from that regardless.
    provider = GroqResearchLanguageModel(api_key="", model="llama-3.3-70b-versatile")
    with pytest.raises(MissingProviderConfigurationError):
        provider.generate(_request())


def test_missing_api_key_error_never_touches_the_sdk():
    # Constructing/instantiating never imports or calls the SDK -- only
    # generate() does, and it must fail BEFORE ever reaching the SDK.
    with patch("groq.Groq") as mock_groq_class:
        provider = GroqResearchLanguageModel(api_key="", model="llama-3.3-70b-versatile")
        with pytest.raises(MissingProviderConfigurationError):
            provider.generate(_request())
        mock_groq_class.assert_not_called()


def test_successful_generation_normalizes_response():
    with patch("groq.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_completion = MagicMock()
        mock_completion.choices = [MagicMock(message=MagicMock(content="  A grounded answer.  "))]
        mock_client.chat.completions.create.return_value = mock_completion

        provider = GroqResearchLanguageModel(api_key="test-key", model="llama-3.3-70b-versatile")
        response = provider.generate(_request())

        assert response.text == "A grounded answer."
        mock_client.chat.completions.create.assert_called_once()
        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs["model"] == "llama-3.3-70b-versatile"
        assert kwargs["messages"][0]["role"] == "system"
        assert kwargs["messages"][1]["role"] == "user"


def test_sdk_failure_wrapped_as_controlled_error():
    with patch("groq.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("network exploded")

        provider = GroqResearchLanguageModel(api_key="test-key", model="llama-3.3-70b-versatile")
        with pytest.raises(ProviderRequestFailedError):
            provider.generate(_request())


def test_model_name_exposed_without_leaking_sdk_object():
    provider = GroqResearchLanguageModel(api_key="test-key", model="llama-3.3-70b-versatile")
    assert provider.model_name == "llama-3.3-70b-versatile"
