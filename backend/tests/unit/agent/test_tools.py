"""Phase 5C: tool wrapper tests -- input validation, deterministic
success shape, and controlled error behavior. No network."""

from __future__ import annotations

from app.agent.tools import (
    audit_strategy_decision,
    get_performance_analytics,
    get_signal_outcomes,
    get_strategy_evaluation,
    investigate_strategy_failures,
    run_backtest,
    search_instruments,
    search_research_knowledge,
)
from tests.unit.agent.conftest import FIXTURE_END, FIXTURE_KNOWN_BUY_DATE, FIXTURE_START


def test_search_instruments_success(deps):
    result = search_instruments({"query": "RELIANCE"}, deps)
    assert result.status == "ok"
    assert result.data["results"][0]["symbol"] == "RELIANCE"


def test_search_instruments_rejects_blank_query(deps):
    result = search_instruments({"query": "   "}, deps)
    assert result.status == "error"
    assert result.error_code == "INVALID_ARGUMENT"


def test_search_instruments_rejects_invalid_limit(deps):
    result = search_instruments({"query": "RELIANCE", "limit": 0}, deps)
    assert result.status == "error"


def test_get_strategy_evaluation_returns_decision_and_conditions(deps):
    result = get_strategy_evaluation(
        {"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END, "target_date": FIXTURE_KNOWN_BUY_DATE}, deps
    )
    assert result.status == "ok"
    assert result.data["decision"] == "BUY"
    assert len(result.data["conditions"]) == 3
    assert result.data["range_summary"]["total"] > 0


def test_get_strategy_evaluation_rejects_missing_symbol(deps):
    result = get_strategy_evaluation({"start": FIXTURE_START, "end": FIXTURE_END}, deps)
    assert result.status == "error"
    assert result.error_code == "INVALID_ARGUMENT"


def test_get_strategy_evaluation_rejects_bad_date(deps):
    result = get_strategy_evaluation({"symbol": "RELIANCE", "start": "not-a-date", "end": FIXTURE_END}, deps)
    assert result.status == "error"
    assert result.error_code == "INVALID_ARGUMENT"


def test_get_strategy_evaluation_rejects_start_after_end(deps):
    result = get_strategy_evaluation({"symbol": "RELIANCE", "start": FIXTURE_END, "end": FIXTURE_START}, deps)
    assert result.status == "error"
    assert result.error_code == "INVALID_DATE_RANGE"


def test_get_signal_outcomes_returns_outcomes(deps):
    result = get_signal_outcomes({"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END}, deps)
    assert result.status == "ok"
    assert result.data["count"] == len(result.data["outcomes"])
    assert result.data["count"] > 0


def test_run_backtest_returns_trades_and_equity_summary(deps):
    result = run_backtest({"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END}, deps)
    assert result.status == "ok"
    assert "equity_curve" not in result.data  # full curve deliberately not exposed
    assert result.data["starting_equity"] == 100_000.0
    assert isinstance(result.data["trades"], list)


def test_run_backtest_rejects_invalid_initial_capital(deps):
    result = run_backtest({"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END, "initial_capital": -5}, deps)
    assert result.status == "error"


def test_get_performance_analytics_returns_metrics(deps):
    result = get_performance_analytics({"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END}, deps)
    assert result.status == "ok"
    assert result.data["closed_trade_count"] >= 0
    assert -1.0 <= (result.data["maximum_drawdown"] or 0.0) <= 0.0


def test_audit_strategy_decision_returns_evidence(deps):
    result = audit_strategy_decision(
        {"symbol": "RELIANCE", "audit_date": FIXTURE_KNOWN_BUY_DATE, "start": FIXTURE_START, "end": FIXTURE_END}, deps
    )
    assert result.status == "ok"
    assert result.data["decision"] in ("BUY", "NO_SIGNAL", "INSUFFICIENT_DATA")
    assert len(result.data["decision_evidence"]) == 3
    assert result.data["point_in_time_context"]["regime"] in ("BULLISH_TREND", "BEARISH_TREND", "TRANSITIONAL", "INSUFFICIENT_DATA")
    assert "hindsight" in result.data["retrospective_hindsight"]["note"].lower()
    assert "available_forward_bars" in result.data["retrospective_hindsight"]


def test_audit_strategy_decision_rejects_non_trading_date(deps):
    result = audit_strategy_decision(
        {"symbol": "RELIANCE", "audit_date": "1999-01-01", "start": FIXTURE_START, "end": FIXTURE_END}, deps
    )
    assert result.status == "error"
    assert result.error_code == "AUDIT_DATE_NOT_A_TRADING_BAR"


def test_investigate_strategy_failures_returns_population(deps):
    result = investigate_strategy_failures({"symbol": "RELIANCE", "start": FIXTURE_START, "end": FIXTURE_END}, deps)
    assert result.status == "ok"
    d = result.data
    assert d["total_signal_count"] == d["eligible_count"] + d["unavailable_count"]
    assert d["eligible_count"] == d["failed_count"] + d["non_failed_count"]
    assert "observations" not in d  # deliberately summarized, not the full per-signal list


def test_search_research_knowledge_returns_provenance(deps):
    result = search_research_knowledge({"query": "What conditions trigger Trend + Momentum v1?"}, deps)
    assert result.status == "ok"
    first = result.data["results"][0]
    for key in ("chunk_id", "document_id", "document_title", "source_path", "section_heading", "trust", "score", "content"):
        assert key in first


def test_search_research_knowledge_rejects_blank_query(deps):
    result = search_research_knowledge({"query": ""}, deps)
    assert result.status == "error"


def test_unknown_symbol_returns_controlled_error_not_traceback(deps):
    result = get_strategy_evaluation({"symbol": "TOTALLY_FAKE_SYMBOL", "start": FIXTURE_START, "end": FIXTURE_END}, deps)
    assert result.status == "error"
    assert result.error_message
    assert "Traceback" not in result.error_message


def test_path_traversal_style_symbol_argument_fails_safely_not_as_filesystem_access(deps):
    result = get_strategy_evaluation({"symbol": "../../.env", "start": FIXTURE_START, "end": FIXTURE_END}, deps)
    assert result.status == "error"
    assert "Traceback" not in (result.error_message or "")
