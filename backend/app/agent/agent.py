"""Phase 5C: the bounded tool-using research agent loop.

`run_research_agent` is the only public entry point. It never lets the
model execute anything beyond the explicit `TOOL_REGISTRY` allowlist,
never persists or exposes chain-of-thought, and always reconstructs
knowledge-source provenance from actual `search_research_knowledge` tool
results -- never from the model's own generated text (see CLAUDE.md
Phase 5C).
"""

from __future__ import annotations

import json

from app.agent.dependencies import AgentDependencies
from app.agent.models import AgentMessage, ResearchAgentResult, ToolTraceEntry
from app.agent.prompt import SYSTEM_INSTRUCTION
from app.agent.provider import ToolCallingLanguageModel
from app.agent.registry import TOOL_REGISTRY, get_tool
from app.agent.sanitize import strip_citation_markers
from app.core.exceptions import AgentInputInvalidError
from app.knowledge.models import SourceReference, TrustClassification

# Centralized, small, bounded -- see CLAUDE.md Phase 5C section 7. Not an
# autonomous loop: the agent always stops within this many tool-calling
# steps, one way or another.
MAX_TOOL_STEPS = 5

_MAX_RESULT_SUMMARY_CHARS = 200


def run_research_agent(
    question: str,
    provider: ToolCallingLanguageModel,
    deps: AgentDependencies,
    max_steps: int = MAX_TOOL_STEPS,
) -> ResearchAgentResult:
    if not question or not question.strip():
        raise AgentInputInvalidError("Question must not be blank.")

    messages: list[AgentMessage] = [
        AgentMessage(role="system", content=SYSTEM_INSTRUCTION),
        AgentMessage(role="user", content=question),
    ]
    tool_trace: list[ToolTraceEntry] = []
    knowledge_sources: dict[str, SourceReference] = {}
    tools = list(TOOL_REGISTRY.values())

    for step in range(max_steps):
        response = provider.generate_step(messages, tools)

        if response.final_text is not None:
            return ResearchAgentResult(
                question=question,
                answer=strip_citation_markers(response.final_text),
                tool_trace=tuple(tool_trace),
                knowledge_sources=tuple(knowledge_sources.values()),
                completed_steps=step,
                stopped_reason="final_answer",
                model=getattr(provider, "model_name", None),
            )

        messages.append(AgentMessage(role="assistant", content="", tool_calls=response.tool_calls))

        for call in response.tool_calls:
            tool = get_tool(call.tool_name)

            if tool is None:
                tool_trace.append(
                    ToolTraceEntry(
                        tool_name=call.tool_name,
                        arguments=call.arguments,
                        status="rejected",
                        result_summary="Unknown tool -- not in the TradeLens tool registry; not executed.",
                    )
                )
                payload = {"status": "error", "error_code": "UNKNOWN_TOOL", "error_message": f"{call.tool_name!r} is not a registered TradeLens tool."}
                messages.append(
                    AgentMessage(role="tool", content=json.dumps(payload), tool_call_id=call.tool_call_id, tool_name=call.tool_name)
                )
                continue

            result = tool.handler(call.arguments, deps)

            if result.status == "ok":
                if tool.name == "search_research_knowledge":
                    for item in result.data.get("results", []):
                        knowledge_sources[item["chunk_id"]] = SourceReference(
                            document_id=item["document_id"],
                            document_title=item["document_title"],
                            source_path=item["source_path"],
                            chunk_id=item["chunk_id"],
                            chunk_ordinal=item["chunk_ordinal"],
                            section_heading=item["section_heading"],
                            trust=TrustClassification(item["trust"]),
                        )
                tool_trace.append(
                    ToolTraceEntry(
                        tool_name=tool.name,
                        arguments=call.arguments,
                        status="ok",
                        result_summary=_summarize(result.data),
                        raw_result=result.data,
                    )
                )
                payload = {"status": "ok", "data": result.data}
            else:
                tool_trace.append(
                    ToolTraceEntry(
                        tool_name=tool.name,
                        arguments=call.arguments,
                        status="error",
                        result_summary=f"{result.error_code}: {result.error_message}",
                    )
                )
                payload = {"status": "error", "error_code": result.error_code, "error_message": result.error_message}

            messages.append(
                AgentMessage(role="tool", content=json.dumps(payload, default=str), tool_call_id=call.tool_call_id, tool_name=tool.name)
            )

    return ResearchAgentResult(
        question=question,
        answer="TradeLens reached its research-step limit before producing a final answer. Try a narrower question.",
        tool_trace=tuple(tool_trace),
        knowledge_sources=tuple(knowledge_sources.values()),
        completed_steps=max_steps,
        stopped_reason="max_steps_reached",
        model=getattr(provider, "model_name", None),
    )


def _summarize(data: dict) -> str:
    summary = json.dumps(data, default=str)
    if len(summary) > _MAX_RESULT_SUMMARY_CHARS:
        summary = summary[:_MAX_RESULT_SUMMARY_CHARS] + "..."
    return summary
