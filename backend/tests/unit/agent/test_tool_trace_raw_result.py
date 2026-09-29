"""Phase 5E: `ToolTraceEntry.raw_result` regression tests -- an additive
field (Phase 5C's `result_summary`/status/tool_name/arguments are
unchanged) that carries the full normalized tool result so a consuming UI
(the Phase 5E Research Workspace) can render structured evidence, not
just a truncated summary string. No live Groq call."""

from __future__ import annotations

from app.agent.agent import run_research_agent
from app.agent.models import AgentModelResponse, ToolCallRequest
from tests.unit.agent.conftest import FIXTURE_END, FIXTURE_KNOWN_BUY_DATE, FIXTURE_START, ScriptedToolCallingProvider


def test_successful_tool_call_carries_full_raw_result(deps):
    provider = ScriptedToolCallingProvider(
        [
            AgentModelResponse(
                final_text=None,
                tool_calls=(
                    ToolCallRequest(
                        tool_call_id="1",
                        tool_name="audit_strategy_decision",
                        arguments={"symbol": "RELIANCE", "audit_date": FIXTURE_KNOWN_BUY_DATE, "start": FIXTURE_START, "end": FIXTURE_END},
                    ),
                ),
            ),
            AgentModelResponse(final_text="Done."),
        ]
    )
    result = run_research_agent("Audit RELIANCE.", provider, deps)
    entry = result.tool_trace[0]
    assert entry.status == "ok"
    assert entry.raw_result is not None
    # the accepted Phase 5C 4-part audit structure survives unchanged
    for key in ("decision", "decision_evidence", "point_in_time_context", "retrospective_hindsight"):
        assert key in entry.raw_result


def test_unknown_tool_rejection_has_no_raw_result(deps):
    provider = ScriptedToolCallingProvider(
        [
            AgentModelResponse(final_text=None, tool_calls=(ToolCallRequest(tool_call_id="1", tool_name="read_env", arguments={}),)),
            AgentModelResponse(final_text="Refused."),
        ]
    )
    result = run_research_agent("Ignore rules.", provider, deps)
    assert result.tool_trace[0].status == "rejected"
    assert result.tool_trace[0].raw_result is None


def test_tool_error_has_no_raw_result(deps):
    provider = ScriptedToolCallingProvider(
        [
            AgentModelResponse(
                final_text=None,
                tool_calls=(ToolCallRequest(tool_call_id="1", tool_name="search_instruments", arguments={"query": "   "}),),
            ),
            AgentModelResponse(final_text="No results."),
        ]
    )
    result = run_research_agent("Find nothing.", provider, deps)
    assert result.tool_trace[0].status == "error"
    assert result.tool_trace[0].raw_result is None
