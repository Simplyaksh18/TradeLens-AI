"""Phase 5F acceptance finding: a live Phase 5E Groq run once claimed no
instrument/symbol was supplied for a question that explicitly named one
("Audit RELIANCE on 2024-06-13..."), with completed_steps=0. Root cause:
model sampling variance at the SDK's default temperature for what is
architecturally a structured tool-selection decision (the tool schema
already marks `symbol` required -- nothing else changed between runs).
Not a schema bug, not a prompt-ambiguity bug in the strict sense, not a
provider outage. Mitigated by (1) temperature=0 on the tool-calling
completion call and (2) an explicit symbol-recognition rule in the system
instruction. Neither eliminates LLM nondeterminism -- these tests verify
only the architecturally enforceable parts. No real Groq call."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from app.agent.models import AgentMessage
from app.agent.prompt import SYSTEM_INSTRUCTION
from app.agent.provider import GroqToolCallingLanguageModel
from app.agent.registry import TOOL_REGISTRY


def test_tool_calling_completion_uses_temperature_zero():
    with patch("groq.Groq") as mock_groq_class:
        mock_client = MagicMock()
        mock_groq_class.return_value = mock_client
        mock_message = MagicMock(content="ok", tool_calls=None)
        mock_client.chat.completions.create.return_value = MagicMock(choices=[MagicMock(message=mock_message)])

        provider = GroqToolCallingLanguageModel(api_key="key", model="openai/gpt-oss-120b")
        provider.generate_step(
            [AgentMessage(role="system", content="sys"), AgentMessage(role="user", content="Audit RELIANCE on 2024-06-13.")],
            list(TOOL_REGISTRY.values()),
        )

        _, kwargs = mock_client.chat.completions.create.call_args
        assert kwargs["temperature"] == 0


def test_system_instruction_tells_model_to_use_a_named_symbol_from_the_question():
    lowered = SYSTEM_INSTRUCTION.lower()
    assert "treat that as the `symbol` argument" in lowered
    assert "do not claim no instrument was specified" in lowered
