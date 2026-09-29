"""Phase 5C hardening regression tests (post manual-acceptance findings --
see CLAUDE.md Phase 5C hardening note).

Manual acceptance found Groq performing financial arithmetic itself
(win rate, average return, trades/month, "positive expectancy") and
introducing unsupported interpretive language (volatility "risk
tolerance", "similar signals", inferential conclusions from a purely
descriptive comparison). We cannot force what an LLM says inside pytest
(no live Groq calls here), so these tests verify the two things that ARE
architecturally enforceable and testable without live calls, per the
hardening instructions ("keep enforcement architectural + prompt/tool-
selection tests", "do not regex-validate every number in prose"):

1. The system instruction and tool descriptions actually state the
   required constraints (text-presence tests -- if a future edit
   silently drops one of these rules, these tests catch it).
2. The deterministic tools genuinely supply the metrics the model would
   otherwise be tempted to compute itself, so grounding without
   arithmetic is always possible when the right tool is called.
"""

from __future__ import annotations

from app.agent.agent import run_research_agent
from app.agent.models import AgentModelResponse, ToolCallRequest
from app.agent.prompt import SYSTEM_INSTRUCTION
from app.agent.registry import TOOL_REGISTRY, get_tool
from tests.unit.agent.conftest import FIXTURE_END, FIXTURE_KNOWN_BUY_DATE, FIXTURE_START, ScriptedToolCallingProvider


def _tool_call(tool_call_id, name, arguments):
    return AgentModelResponse(final_text=None, tool_calls=(ToolCallRequest(tool_call_id, name, arguments),))


def _final(text):
    return AgentModelResponse(final_text=text)


# ---------------------------------------------------------------------------
# 1 & 2. Numeric fidelity / no-arithmetic contract is stated explicitly
# ---------------------------------------------------------------------------


def test_synthesis_prompt_states_required_numeric_fidelity_sentence():
    required_sentence = (
        "Do not perform arithmetic on tool outputs. A numerical value may be "
        "reported only when that value is explicitly present in deterministic "
        "tool evidence. Do not derive a new numerical value."
    )
    assert required_sentence in SYSTEM_INSTRUCTION


def test_synthesis_prompt_forbids_specific_derived_metrics():
    lowered = SYSTEM_INSTRUCTION.lower()
    for phrase in ("win rate", "trades-per-month", "expectancy", "never infer a missing risk statistic"):
        assert phrase in lowered, f"missing required rule text: {phrase!r}"


def test_synthesis_prompt_directs_missing_metric_to_correct_tool_or_explicit_unavailability():
    assert "call the appropriate tool that" in SYSTEM_INSTRUCTION.lower() or "call the appropriate approved deterministic tool" in SYSTEM_INSTRUCTION.lower()
    assert "state plainly that the current evidence does not provide it" in SYSTEM_INSTRUCTION.lower()


# ---------------------------------------------------------------------------
# 3. Audit-language contract: no volatility "tolerance", no "similar
#    signals", no performance-premise claims
# ---------------------------------------------------------------------------


def test_synthesis_prompt_forbids_undocumented_strategy_premises():
    lowered = SYSTEM_INSTRUCTION.lower()
    assert "risk parameters are designed to accommodate" in lowered
    assert "performs best" in lowered


def test_synthesis_prompt_forbids_similar_signals_language():
    assert '"similar"' in SYSTEM_INSTRUCTION or "similar" in SYSTEM_INSTRUCTION.lower()
    assert "no accepted similarity-matching method" in SYSTEM_INSTRUCTION.lower()


def test_audit_tool_result_contains_no_interpretive_fields(deps):
    from app.agent.tools import audit_strategy_decision

    result = audit_strategy_decision(
        {"symbol": "RELIANCE", "audit_date": FIXTURE_KNOWN_BUY_DATE, "start": FIXTURE_START, "end": FIXTURE_END}, deps
    )
    assert result.status == "ok"
    forbidden_keys = {"risk_tolerance", "similar_signals", "interpretation", "recommendation"}
    assert forbidden_keys.isdisjoint(result.data.keys())


# ---------------------------------------------------------------------------
# 4. Failure-investigation language contract: descriptive only
# ---------------------------------------------------------------------------


def test_synthesis_prompt_forbids_inferential_conclusions_from_descriptive_comparison():
    lowered = SYSTEM_INSTRUCTION.lower()
    assert "does not differentiate the populations" in lowered
    assert "no significance-testing method exists" in lowered


def test_investigate_tool_result_contains_no_inferential_fields(deps):
    from app.agent.tools import investigate_strategy_failures

    result = investigate_strategy_failures({"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END}, deps)
    assert result.status == "ok"
    forbidden_keys = {"significance", "p_value", "differentiates", "conclusion"}
    assert forbidden_keys.isdisjoint(result.data.keys())


# ---------------------------------------------------------------------------
# 5. Backtest tool-orchestration division of responsibility
# ---------------------------------------------------------------------------


def test_run_backtest_description_disclaims_derived_metrics():
    tool = get_tool("run_backtest")
    lowered = tool.description.lower()
    assert "does not return win rate" in lowered or "does not return" in lowered
    assert "get_performance_analytics" in tool.description


def test_get_performance_analytics_description_states_authority():
    tool = get_tool("get_performance_analytics")
    lowered = tool.description.lower()
    assert "authoritative" in lowered
    assert "win_rate" in tool.description
    assert "maximum_drawdown" in tool.description


def test_get_performance_analytics_actually_returns_the_metrics_the_model_might_otherwise_compute(deps):
    from app.agent.tools import get_performance_analytics

    result = get_performance_analytics({"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END}, deps)
    assert result.status == "ok"
    for field in ("win_rate", "total_return", "maximum_drawdown", "exposure", "average_trade_return"):
        assert field in result.data  # grounding without arithmetic is always possible


def test_performance_question_flow_traces_deterministic_analytics_call(deps):
    """Scripted flow where the model (correctly) asks for run_backtest THEN
    get_performance_analytics rather than computing a summary from trades
    -- verifies the agent surfaces get_performance_analytics's exact
    deterministic fields in the trace available for grounding."""
    provider = ScriptedToolCallingProvider(
        [
            _tool_call("c1", "run_backtest", {"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END}),
            _tool_call("c2", "get_performance_analytics", {"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END}),
            _final("Performance summary grounded in get_performance_analytics."),
        ]
    )
    result = run_research_agent("Summarize RELIANCE's backtest performance.", provider, deps)
    assert result.stopped_reason == "final_answer"
    analytics_entry = next(t for t in result.tool_trace if t.tool_name == "get_performance_analytics")
    assert analytics_entry.status == "ok"
    assert "win_rate" in analytics_entry.result_summary or "total_return" in analytics_entry.result_summary


# ---------------------------------------------------------------------------
# 6. Missing metric -> correct tool or explicit unavailability (no
#    fabrication path exists architecturally)
# ---------------------------------------------------------------------------


def test_missing_metric_scenario_never_fabricates_a_result(deps):
    """If the model only calls run_backtest (never get_performance_analytics)
    for a performance question, the agent still only ever surfaces exactly
    what run_backtest returned (raw trades/equity) -- no derived field is
    silently injected by application code."""
    provider = ScriptedToolCallingProvider(
        [
            _tool_call("c1", "run_backtest", {"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END}),
            _final("The current evidence does not provide a win rate; only trade-level execution data was retrieved."),
        ]
    )
    result = run_research_agent("What was RELIANCE's win rate?", provider, deps)
    trace_entry = result.tool_trace[0]
    assert "win_rate" not in trace_entry.result_summary  # run_backtest genuinely never returns it


# ---------------------------------------------------------------------------
# 7. Existing allowlist/tool safety unchanged by this hardening
# ---------------------------------------------------------------------------


def test_registry_unchanged_by_hardening():
    assert set(TOOL_REGISTRY.keys()) == {
        "search_instruments",
        "get_strategy_evaluation",
        "get_signal_outcomes",
        "run_backtest",
        "get_performance_analytics",
        "audit_strategy_decision",
        "investigate_strategy_failures",
        "search_research_knowledge",
    }


def test_unregistered_tool_still_rejected_after_prompt_hardening(deps):
    provider = ScriptedToolCallingProvider([_tool_call("c1", "compute_win_rate", {}), _final("Refused.")])
    result = run_research_agent("Compute the win rate yourself.", provider, deps)
    assert result.tool_trace[0].status == "rejected"
