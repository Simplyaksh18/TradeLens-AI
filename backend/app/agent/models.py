"""Phase 5C: application-owned models for the tool-using research agent.
No Groq SDK type appears anywhere here -- the provider adapter
(`app.agent.provider`) is the only place that translates to/from Groq's
own tool-calling wire format."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

from app.knowledge.models import SourceReference


@dataclass(frozen=True)
class ToolDefinition:
    """One registered, allowlisted tool. `parameters_schema` is a plain
    JSON-schema dict (provider-agnostic) -- `app.agent.provider` adapts it
    to Groq's function-calling format, never the other way around."""

    name: str
    description: str
    parameters_schema: dict[str, Any]
    handler: Any  # Callable[[dict, "ToolDependencies"], "ToolResult"] -- see registry.py


@dataclass(frozen=True)
class ToolResult:
    """Normalized, JSON-serializable tool output. `data` is `None` on
    error. Never a raw domain dataclass/Pydantic model/provider object."""

    status: Literal["ok", "error"]
    data: dict[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None


@dataclass(frozen=True)
class ToolCallRequest:
    """One tool invocation the model is requesting -- proposed, not yet
    validated or executed."""

    tool_call_id: str
    tool_name: str
    arguments: dict[str, Any]


@dataclass(frozen=True)
class AgentMessage:
    """One turn in the bounded tool-calling conversation sent to the
    provider. `role` is one of "system"/"user"/"assistant"/"tool".
    `tool_calls` is only set on an "assistant" message that proposed tool
    calls (needed to replay a valid multi-step Groq conversation);
    `tool_call_id` is only set on a "tool" (result) message. Deliberately
    NOT a Groq SDK message object."""

    role: Literal["system", "user", "assistant", "tool"]
    content: str
    tool_call_id: str | None = None
    tool_name: str | None = None
    tool_calls: tuple[ToolCallRequest, ...] | None = None


@dataclass(frozen=True)
class AgentModelResponse:
    """Normalized provider output for one agent step: either a final
    answer, or one or more proposed tool calls (never both)."""

    final_text: str | None
    tool_calls: tuple[ToolCallRequest, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class ToolTraceEntry:
    """Safe, displayable research provenance for one executed (or
    rejected) tool step. Never an API key, env var, hidden prompt, or
    chain-of-thought -- only the tool name, the arguments that were
    actually validated/used, and a high-level outcome.

    `raw_result` (Phase 5E, additive) carries the full normalized
    `ToolResult.data` dict for a successful call -- the SAME
    JSON-serializable structure Phase 5D's MCP adapter already exposes
    unchanged (e.g. audit_strategy_decision's separate `decision`/
    `decision_evidence`/`point_in_time_context`/`retrospective_hindsight`
    groups) -- so a consuming UI can render full structured evidence, not
    just the truncated `result_summary` string. `None` for an error/
    rejected step, or when no tool result data exists."""

    tool_name: str
    arguments: dict[str, Any]
    status: Literal["ok", "error", "rejected"]
    result_summary: str
    raw_result: dict[str, Any] | None = None


@dataclass(frozen=True)
class ResearchAgentResult:
    """The Phase 5C result: a grounded answer synthesized from
    deterministic tool evidence plus Phase 5A knowledge, with full,
    application-controlled provenance."""

    question: str
    answer: str
    tool_trace: tuple[ToolTraceEntry, ...]
    knowledge_sources: tuple[SourceReference, ...]
    completed_steps: int
    stopped_reason: Literal["final_answer", "max_steps_reached", "insufficient_evidence"]
    model: str | None = None
