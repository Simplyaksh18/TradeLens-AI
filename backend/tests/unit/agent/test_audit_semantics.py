"""Phase 5C final hardening: audit_strategy_decision semantic-boundary
regression tests (see CLAUDE.md Phase 5C final hardening note).

Manual acceptance found the live LLM incorrectly describing the Phase 3
Strategy Auditor as "combining" historical hit rates/returns/regime/
volatility/retrospective outcome to produce or justify the BUY decision,
and using the retrospective 10-bar return to "reinforce" it. TradeLens's
Trend + Momentum v1 decision is determined ONLY by the three accepted
strategy conditions (close>SMA20, SMA20>SMA50, 40<=RSI14<=70) --
everything else the audit tool returns is either point-in-time CONTEXT
around an already-determined decision, or HINDSIGHT that was not knowable
at decision time. Neither may justify/reinforce/validate the decision.

As with the other Phase 5C hardening rounds, we cannot force LLM wording
inside pytest -- these tests verify the two architecturally enforceable
things: the tool result is structured/labeled to make this boundary
explicit (decision_evidence vs. point_in_time_context vs.
retrospective_hindsight), and the system instruction states the
constraint in words. No live Groq calls."""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from app.agent.prompt import SYSTEM_INSTRUCTION
from app.agent.registry import get_tool
from app.agent.tools import audit_strategy_decision
from tests.unit.agent.conftest import FIXTURE_END, FIXTURE_KNOWN_BUY_DATE, FIXTURE_START


def _audit(deps):
    result = audit_strategy_decision(
        {"symbol": "RELIANCE", "audit_date": FIXTURE_KNOWN_BUY_DATE, "start": FIXTURE_START, "end": FIXTURE_END}, deps
    )
    assert result.status == "ok"
    return result.data


# ---------------------------------------------------------------------------
# Tool-result structure: decision vs. context vs. hindsight kept distinct
# ---------------------------------------------------------------------------


def test_buy_decision_comes_from_deterministic_decision_evidence(deps):
    data = _audit(deps)
    assert data["decision"] in ("BUY", "NO_SIGNAL", "INSUFFICIENT_DATA")
    assert len(data["decision_evidence"]) == 3
    condition_ids = {c["condition_id"] for c in data["decision_evidence"]}
    assert len(condition_ids) == 3  # the three accepted strategy conditions, nothing invented


def test_historical_hit_rates_are_nested_under_context_not_top_level(deps):
    data = _audit(deps)
    assert "five_bar_hit_rate" not in data
    assert "ten_bar_hit_rate" not in data
    assert "five_bar_hit_rate" in data["point_in_time_context"]
    assert "ten_bar_hit_rate" in data["point_in_time_context"]


def test_regime_is_nested_under_context_not_top_level(deps):
    data = _audit(deps)
    assert "regime" not in data
    assert "regime" in data["point_in_time_context"]


def test_volatility_is_nested_under_context_not_top_level(deps):
    data = _audit(deps)
    assert "annualized_realized_volatility_20" not in data
    assert "annualized_realized_volatility_20" in data["point_in_time_context"]


def test_retrospective_outcome_is_nested_and_labeled_as_hindsight(deps):
    data = _audit(deps)
    assert "retrospective_forward_return_10d" not in data  # old flat key removed
    hindsight = data["retrospective_hindsight"]
    assert "forward_return_10d" in hindsight
    note = hindsight["note"].lower()
    assert "hindsight" in note
    assert "not available at decision time" in note
    assert "does not justify" in note or "not justify" in note


# ---------------------------------------------------------------------------
# Tool description states the boundary explicitly
# ---------------------------------------------------------------------------


def test_tool_description_states_decision_is_deterministic_from_evidence_only():
    tool = get_tool("audit_strategy_decision")
    lowered = tool.description.lower()
    assert "determined only by" in lowered or "determined  only by" in lowered
    assert "decision_evidence" in tool.description


def test_tool_description_states_context_does_not_determine_decision():
    tool = get_tool("audit_strategy_decision")
    lowered = tool.description.lower()
    assert "does not determine, justify, produce, or explain" in lowered


def test_tool_description_states_hindsight_must_never_justify():
    tool = get_tool("audit_strategy_decision")
    lowered = tool.description.lower()
    assert "not knowable at decision time" in lowered
    assert "must never be described as justifying" in lowered


# ---------------------------------------------------------------------------
# System instruction states the audit semantic boundary
# ---------------------------------------------------------------------------


def test_system_instruction_forbids_context_justifying_decision():
    lowered = SYSTEM_INSTRUCTION.lower()
    assert "already-determined decision" in lowered
    assert "the historical hit rate justifies the decision" in lowered


def test_system_instruction_forbids_hindsight_reinforcing_decision():
    lowered = SYSTEM_INSTRUCTION.lower()
    assert "reinforces" in lowered or "reinforcing" in lowered
    assert "never say the forward return" in lowered


def test_system_instruction_forbids_undocumented_volatility_calibration():
    lowered = SYSTEM_INSTRUCTION.lower()
    assert "within strategy tolerance" in lowered
    assert "calibrated for" in lowered


def test_system_instruction_forbids_regime_performance_claim():
    lowered = SYSTEM_INSTRUCTION.lower()
    assert 'performs best' in lowered


def test_system_instruction_explains_decision_must_use_only_decision_evidence():
    lowered = SYSTEM_INSTRUCTION.lower()
    assert "explain why the decision occurred using only decision_evidence" in lowered
