"""Phase 5C: the tool-calling provider boundary. `ToolCallingLanguageModel`
extends (additively -- see CLAUDE.md Phase 5C) the accepted Phase 5B
provider concept without modifying `app.ai.provider` at all.
`GroqToolCallingLanguageModel` subclasses the accepted
`GroqResearchLanguageModel` to reuse its lazy client construction and
`GROQ_API_KEY`/model configuration unchanged, adding ONLY Groq's native
tool/function-calling request-response translation. No Groq SDK message,
tool, or completion object crosses out of this module."""

from __future__ import annotations

import json
import uuid
from abc import ABC, abstractmethod
from collections.abc import Sequence

from app.agent.models import AgentMessage, AgentModelResponse, ToolCallRequest, ToolDefinition
from app.ai.provider import GroqResearchLanguageModel
from app.core.exceptions import MissingProviderConfigurationError, ProviderRateLimitedError, ProviderRequestFailedError


class ToolCallingLanguageModel(ABC):
    """Conceptual interface every tool-calling-capable provider
    implements. `messages`/`tools`/the returned `AgentModelResponse` are
    all application-owned (`app.agent.models`) -- never a Groq SDK type."""

    @abstractmethod
    def generate_step(self, messages: Sequence[AgentMessage], tools: Sequence[ToolDefinition]) -> AgentModelResponse: ...


class GroqToolCallingLanguageModel(GroqResearchLanguageModel, ToolCallingLanguageModel):
    """Groq-backed `ToolCallingLanguageModel`. Reuses
    `GroqResearchLanguageModel.__init__`/`_get_client`/`model_name`
    unchanged -- this class ONLY adds `generate_step`."""

    def generate_step(self, messages: Sequence[AgentMessage], tools: Sequence[ToolDefinition]) -> AgentModelResponse:
        if not self._api_key:
            raise MissingProviderConfigurationError(
                "GROQ_API_KEY is not configured. Set it in backend/.env "
                "(server-side only -- see backend/.env.example) before "
                "invoking the Groq tool-calling research agent."
            )

        client = self._get_client()
        groq_messages = [_to_groq_message(message) for message in messages]
        groq_tools = [_to_groq_tool(tool) for tool in tools]

        try:
            completion = client.chat.completions.create(
                model=self._model,
                messages=groq_messages,
                tools=groq_tools,
                tool_choice="auto",
                # Phase 5F: temperature=0 for the tool-selection/synthesis
                # step. Tool selection over a fixed, schema-validated
                # registry is closer to a structured-decision task than
                # free creative writing -- a live Phase 5E acceptance run
                # showed the model (at the SDK's default, higher
                # temperature) once claiming no symbol was supplied for a
                # question that explicitly named one, purely due to
                # sampling variance (the tool schema already marks
                # `symbol` required; nothing else in the request changed
                # between runs). This does not make Groq deterministic
                # (no seed/fixed-infrastructure guarantee exists), but
                # measurably reduces run-to-run variance for this
                # structured task. See CLAUDE.md Phase 5F tool-selection
                # nondeterminism finding.
                temperature=0,
            )
        except Exception as exc:  # narrow re-raise; never leak the SDK exception type
            from groq import RateLimitError  # imported lazily, same convention as _get_client()

            if isinstance(exc, RateLimitError):
                retry_after = _extract_retry_after_seconds(exc)
                suffix = f" Retry after approximately {retry_after} seconds." if retry_after is not None else ""
                raise ProviderRateLimitedError(f"Groq rate/quota limit reached.{suffix}") from exc
            raise ProviderRequestFailedError(f"Groq tool-calling request failed: {exc}") from exc

        message = completion.choices[0].message if completion.choices else None
        if message is None:
            return AgentModelResponse(final_text="")

        raw_tool_calls = getattr(message, "tool_calls", None) or []
        if raw_tool_calls:
            tool_calls = tuple(
                ToolCallRequest(
                    tool_call_id=call.id or str(uuid.uuid4()),
                    tool_name=call.function.name,
                    arguments=_parse_arguments(call.function.arguments),
                )
                for call in raw_tool_calls
            )
            return AgentModelResponse(final_text=None, tool_calls=tool_calls)

        return AgentModelResponse(final_text=(message.content or "").strip())


def _to_groq_message(message: AgentMessage) -> dict:
    if message.role == "tool":
        return {"role": "tool", "tool_call_id": message.tool_call_id, "content": message.content}
    if message.role == "assistant" and message.tool_calls:
        return {
            "role": "assistant",
            "content": message.content or None,
            "tool_calls": [
                {
                    "id": call.tool_call_id,
                    "type": "function",
                    "function": {"name": call.tool_name, "arguments": json.dumps(call.arguments)},
                }
                for call in message.tool_calls
            ],
        }
    return {"role": message.role, "content": message.content}


def _to_groq_tool(tool: ToolDefinition) -> dict:
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": tool.parameters_schema,
        },
    }


def _parse_arguments(raw_arguments: str) -> dict:
    try:
        parsed = json.loads(raw_arguments) if raw_arguments else {}
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _extract_retry_after_seconds(exc: object) -> float | None:
    """Best-effort, defensive read of the standard HTTP `Retry-After`
    response header from a Groq `RateLimitError`. Returns `None` (never
    raises) if the header is absent or unparsable -- this is a UX hint
    only, never load-bearing. Never reads/logs any other header (e.g. no
    Authorization/API-key material is ever present in this header
    anyway)."""

    try:
        header_value = exc.response.headers.get("retry-after")  # type: ignore[attr-defined]
        return float(header_value) if header_value is not None else None
    except Exception:
        return None
