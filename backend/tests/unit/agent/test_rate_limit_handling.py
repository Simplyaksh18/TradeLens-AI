"""Phase 5E rate-limit diagnosis fix: a genuine Groq HTTP 429
(`groq.RateLimitError`) must be distinguished from a generic provider
failure so the API/frontend can show accurate copy instead of the
generic "provider unavailable" message (see CLAUDE.md Phase 5E rate-
limit diagnosis). No real Groq/network call -- `groq.Groq` is mocked and
a real `groq.RateLimitError` is constructed locally with a synthetic
httpx.Response, exactly matching the SDK's own exception shape."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import httpx
import pytest
from groq import RateLimitError

from app.agent.models import AgentMessage
from app.agent.provider import GroqToolCallingLanguageModel, _extract_retry_after_seconds
from app.agent.registry import TOOL_REGISTRY
from app.core.exceptions import ProviderRateLimitedError, ProviderRequestFailedError


def _messages():
    return [AgentMessage(role="system", content="sys"), AgentMessage(role="user", content="hello")]


def _rate_limit_error(retry_after: str | None) -> RateLimitError:
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    headers = {"retry-after": retry_after} if retry_after is not None else {}
    response = httpx.Response(429, headers=headers, request=request)
    return RateLimitError("Rate limit reached.", response=response, body=None)


def test_groq_rate_limit_error_raises_provider_rate_limited_error_not_generic_failure():
    with patch("groq.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = _rate_limit_error("30")

        provider = GroqToolCallingLanguageModel(api_key="key", model="openai/gpt-oss-120b")
        with pytest.raises(ProviderRateLimitedError):
            provider.generate_step(_messages(), list(TOOL_REGISTRY.values()))


def test_provider_rate_limited_error_is_a_provider_request_failed_error_subclass():
    # so any existing broader-failure handling still applies (see core/exceptions.py docstring)
    assert issubclass(ProviderRateLimitedError, ProviderRequestFailedError)


def test_rate_limit_error_message_includes_retry_after_hint_when_present():
    with patch("groq.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = _rate_limit_error("45")

        provider = GroqToolCallingLanguageModel(api_key="key", model="openai/gpt-oss-120b")
        with pytest.raises(ProviderRateLimitedError) as exc_info:
            provider.generate_step(_messages(), list(TOOL_REGISTRY.values()))
        assert "45" in str(exc_info.value)


def test_non_rate_limit_sdk_failure_still_maps_to_generic_provider_error():
    with patch("groq.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("boom")

        provider = GroqToolCallingLanguageModel(api_key="key", model="openai/gpt-oss-120b")
        with pytest.raises(ProviderRequestFailedError) as exc_info:
            provider.generate_step(_messages(), list(TOOL_REGISTRY.values()))
        assert not isinstance(exc_info.value, ProviderRateLimitedError)


def test_extract_retry_after_seconds_missing_header_returns_none():
    error = _rate_limit_error(None)
    assert _extract_retry_after_seconds(error) is None


def test_extract_retry_after_seconds_malformed_header_returns_none_not_raises():
    request = httpx.Request("POST", "https://api.groq.com/openai/v1/chat/completions")
    response = httpx.Response(429, headers={"retry-after": "not-a-number"}, request=request)
    error = RateLimitError("Rate limit reached.", response=response, body=None)
    assert _extract_retry_after_seconds(error) is None
