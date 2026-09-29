"""Phase 5C: GroqToolCallingLanguageModel adapter tests. The Groq SDK is
always mocked -- no real network call."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.agent.models import AgentMessage, ToolCallRequest
from app.agent.provider import GroqToolCallingLanguageModel
from app.agent.registry import TOOL_REGISTRY
from app.core.exceptions import MissingProviderConfigurationError, ProviderRequestFailedError


def _messages():
    return [AgentMessage(role="system", content="sys"), AgentMessage(role="user", content="hello")]


def test_missing_api_key_raises_controlled_error():
    provider = GroqToolCallingLanguageModel(api_key="", model="openai/gpt-oss-120b")
    with pytest.raises(MissingProviderConfigurationError):
        provider.generate_step(_messages(), list(TOOL_REGISTRY.values()))


def test_final_text_response_normalized():
    with patch("groq.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_message = MagicMock(content="Final answer.", tool_calls=None)
        mock_client.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=mock_message)])

        provider = GroqToolCallingLanguageModel(api_key="key", model="openai/gpt-oss-120b")
        response = provider.generate_step(_messages(), list(TOOL_REGISTRY.values()))

        assert response.final_text == "Final answer."
        assert response.tool_calls == ()
        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs["tool_choice"] == "auto"
        assert len(kwargs["tools"]) == len(TOOL_REGISTRY)
        assert kwargs["tools"][0]["type"] == "function"


def test_tool_call_response_normalized():
    with patch("groq.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        fake_call = MagicMock()
        fake_call.id = "call_1"
        fake_call.function.name = "search_research_knowledge"
        fake_call.function.arguments = '{"query": "BUY rule"}'
        mock_message = MagicMock(content=None, tool_calls=[fake_call])
        mock_client.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=mock_message)])

        provider = GroqToolCallingLanguageModel(api_key="key", model="openai/gpt-oss-120b")
        response = provider.generate_step(_messages(), list(TOOL_REGISTRY.values()))

        assert response.final_text is None
        assert len(response.tool_calls) == 1
        assert response.tool_calls[0].tool_name == "search_research_knowledge"
        assert response.tool_calls[0].arguments == {"query": "BUY rule"}


def test_malformed_tool_arguments_json_degrades_to_empty_dict():
    with patch("groq.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        fake_call = MagicMock()
        fake_call.id = "call_1"
        fake_call.function.name = "search_instruments"
        fake_call.function.arguments = "{not valid json"
        mock_message = MagicMock(content=None, tool_calls=[fake_call])
        mock_client.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=mock_message)])

        provider = GroqToolCallingLanguageModel(api_key="key", model="openai/gpt-oss-120b")
        response = provider.generate_step(_messages(), list(TOOL_REGISTRY.values()))

        assert response.tool_calls[0].arguments == {}


def test_sdk_failure_wrapped_as_controlled_error():
    with patch("groq.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_client.chat.completions.create.side_effect = RuntimeError("boom")

        provider = GroqToolCallingLanguageModel(api_key="key", model="openai/gpt-oss-120b")
        with pytest.raises(ProviderRequestFailedError):
            provider.generate_step(_messages(), list(TOOL_REGISTRY.values()))


def test_assistant_message_with_tool_calls_replays_correctly():
    with patch("groq.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_message = MagicMock(content="ok", tool_calls=None)
        mock_client.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=mock_message)])

        provider = GroqToolCallingLanguageModel(api_key="key", model="openai/gpt-oss-120b")
        history = [
            *_messages(),
            AgentMessage(
                role="assistant",
                content="",
                tool_calls=(ToolCallRequest(tool_call_id="call_1", tool_name="search_instruments", arguments={"query": "x"}),),
            ),
            AgentMessage(role="tool", content='{"status": "ok"}', tool_call_id="call_1", tool_name="search_instruments"),
        ]
        provider.generate_step(history, list(TOOL_REGISTRY.values()))

        _, kwargs = mock_client.chat.completions.create.call_args
        assistant_msg = kwargs["messages"][2]
        assert assistant_msg["role"] == "assistant"
        assert assistant_msg["tool_calls"][0]["function"]["name"] == "search_instruments"
        tool_msg = kwargs["messages"][3]
        assert tool_msg["role"] == "tool"
        assert tool_msg["tool_call_id"] == "call_1"
