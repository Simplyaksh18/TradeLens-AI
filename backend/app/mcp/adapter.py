"""Phase 5D: pure adapter between the accepted Phase 5C tool registry
(`app.agent.registry.TOOL_REGISTRY`) and the MCP wire types. Performs ZERO
financial calculation, ZERO interpretation, and ZERO dynamic name
resolution -- every tool call is looked up in `TOOL_REGISTRY` (never
imported/resolved by name) and executed through the exact same
`ToolDefinition.handler` the Phase 5C Groq agent already uses. Importing
this module never starts a server and never requires GROQ_API_KEY."""

from __future__ import annotations

import json

from mcp import types

from app.agent.dependencies import AgentDependencies
from app.agent.models import ToolResult
from app.agent.registry import TOOL_REGISTRY

# Tools carry no side effects on TradeLens state (market data / knowledge
# base are read-only from the agent's perspective) and their output
# depends only on their arguments -- safe to mark read-only/idempotent so
# an MCP client can reason about them, and explicitly non-destructive/
# non-open-world (no filesystem/network-arbitrary access, see CLAUDE.md
# Phase 5D security boundary).
_TOOL_ANNOTATIONS = types.ToolAnnotations(
    readOnlyHint=True,
    destructiveHint=False,
    idempotentHint=True,
    openWorldHint=False,
)


def list_mcp_tools() -> list[types.Tool]:
    """One `types.Tool` per registered Phase 5C `ToolDefinition`, in
    registry order. Name/description/input schema are taken directly from
    the accepted `ToolDefinition` -- never redefined or duplicated here."""

    return [
        types.Tool(
            name=tool.name,
            description=tool.description,
            inputSchema=tool.parameters_schema,
            annotations=_TOOL_ANNOTATIONS,
        )
        for tool in TOOL_REGISTRY.values()
    ]


def _tool_result_to_call_result(result: ToolResult) -> types.CallToolResult:
    """Serializes a `ToolResult` into an MCP `CallToolResult` without
    altering any field TradeLens's own tool handler already produced --
    no rounding, no renaming, no flattening of the accepted audit
    decision/decision_evidence/point_in_time_context/
    retrospective_hindsight structure, no rewriting of
    search_research_knowledge provenance."""

    if result.status == "ok":
        data = result.data if result.data is not None else {}
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(data, indent=2))],
            structuredContent=data,
            isError=False,
        )
    # Controlled application error (invalid arguments, unknown symbol,
    # domain input-contract violation, etc.) -- reported as an MCP tool
    # error with the same safe code/message the Phase 5C agent already
    # receives, never a raw traceback/exception internals.
    error_payload = {"error_code": result.error_code, "error_message": result.error_message}
    return types.CallToolResult(
        content=[types.TextContent(type="text", text=json.dumps(error_payload, indent=2))],
        structuredContent=error_payload,
        isError=True,
    )


def call_mcp_tool(name: str, arguments: dict, deps: AgentDependencies) -> types.CallToolResult:
    """Executes exactly `TOOL_REGISTRY[name].handler(arguments, deps)` --
    the SAME registered handler the Phase 5C Groq agent uses -- and
    returns a safe MCP result. `name` is looked up in `TOOL_REGISTRY`
    only; a name that is not present is REJECTED here and never resolved
    dynamically (mirrors `app.agent.agent.run_research_agent`'s own
    allowlist-only behavior, see CLAUDE.md Phase 5C section 5 / Phase 5D
    security boundary)."""

    tool = TOOL_REGISTRY.get(name)
    if tool is None:
        error_payload = {"error_code": "UNKNOWN_TOOL", "error_message": f"{name!r} is not a registered TradeLens tool."}
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(error_payload, indent=2))],
            structuredContent=error_payload,
            isError=True,
        )

    try:
        result = tool.handler(arguments, deps)
    except Exception as exc:  # last-resort containment -- see app.agent.tools's own handler contract
        error_payload = {"error_code": "TOOL_EXECUTION_FAILED", "error_message": f"{exc.__class__.__name__}: {exc}"}
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=json.dumps(error_payload, indent=2))],
            structuredContent=error_payload,
            isError=True,
        )

    return _tool_result_to_call_result(result)
