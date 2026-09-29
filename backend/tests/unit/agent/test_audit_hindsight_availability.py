"""Generic, multi-symbol regression proof for audit_strategy_decision's
retrospective-hindsight availability (see CLAUDE.md "Audit Contract" --
Post-5F Research Workspace acceptance issue: SBIN 2025-03-24 correctly
showed no retrospective outcome because the audited decision was
NO_SIGNAL, not a bug -- but the tool result gave no machine-readable
reason to distinguish that from a genuine BUY-with-censored-outcome case).

No symbol, date, or numeric value used here is hardcoded to any manual
verification case (SBIN/RELIANCE/TATASTEEL/2024-06-13/2025-03-24) -- every
date used is DISCOVERED by scanning a deterministically generated series
for the first bar matching the required decision, for TWO different
arbitrary symbols, proving the behavior is generic rather than coincidental
to one instrument.
"""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.agent.dependencies import AgentDependencies
from app.agent.tools import audit_strategy_decision
from app.indicators.engine import compute_indicators
from app.knowledge.embedding import LocalHashEmbeddingProvider
from app.knowledge.retriever import ResearchKnowledgeRetriever
from app.knowledge.vector_store import InMemoryVectorStore
from app.market_data.models import OHLCVBar, OHLCVSeries
from app.outcomes.engine import compute_signal_outcomes
from app.strategies.engine import evaluate_strategy
from app.strategies.models import StrategyDecision
from tests.unit.agent.conftest import FakeInstrumentMaster, FakeMarketDataService

# Two arbitrary, otherwise-uninvolved instruments -- neither appears in any
# other manual-verification fixture in this project. Chosen only to prove
# genericity across symbols, never to encode symbol-specific behavior.
_SYMBOL_A = "ARBITRARYONE"
_SYMBOL_B = "ARBITRARYTWO"


def _make_series(provider_symbol: str, n: int = 260, start: date = date(2023, 1, 2)) -> OHLCVSeries:
    """Same repeating ascend/descend cycle shape already established as
    producing genuine BUY/NO_SIGNAL/INSUFFICIENT_DATA signals (see
    `tests/unit/agent/conftest.py::_make_repeating_cycle_series`), just
    parameterized by symbol/length here so this file owns no
    symbol-specific behavior of its own."""
    closes: list[float] = []
    close = 100.0
    cycle_len = 90
    for i in range(n):
        pos = i % cycle_len
        if pos < 50:
            close += 0.01
        elif pos < 65:
            close += 3.0
        else:
            close -= 3.0
        closes.append(close)
    bars = tuple(
        OHLCVBar(date=start + timedelta(days=i), open=c, high=c + 2, low=c - 2, close=c, adj_close=c, volume=1000)
        for i, c in enumerate(closes)
    )
    return OHLCVSeries(provider_symbol=provider_symbol, interval="1d", bars=bars)


def _deps_for(series: OHLCVSeries, bare_symbol: str) -> AgentDependencies:
    retriever = ResearchKnowledgeRetriever(LocalHashEmbeddingProvider(), InMemoryVectorStore())
    retriever.index_corpus()
    return AgentDependencies(
        market_data_service=FakeMarketDataService(series, known_symbols=frozenset({bare_symbol})),
        instrument_master=FakeInstrumentMaster(),
        knowledge_retriever=retriever,
    )


def _find_date(series: OHLCVSeries, decision: StrategyDecision, min_future_bars: int = 0) -> date:
    """Scans the REAL, accepted indicator/strategy engines (never a hand-
    faked decision) for the first bar matching `decision` with at least
    `min_future_bars` bars remaining after it in `series`."""
    indicators = compute_indicators(series)
    evaluations = evaluate_strategy(series, indicators)
    for i, ev in enumerate(evaluations.evaluations):
        if ev.decision == decision and (len(series.bars) - 1 - i) >= min_future_bars:
            return ev.date
    raise AssertionError(f"No {decision} bar with >= {min_future_bars} future bars found in fixture")


# ---------------------------------------------------------------------------
# Case A: BUY + >= 10 future bars -> retrospective 10-bar outcome available
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("symbol,provider_symbol", [(_SYMBOL_A, f"{_SYMBOL_A}.NS"), (_SYMBOL_B, f"{_SYMBOL_B}.NS")])
def test_case_a_buy_with_full_forward_window_has_available_hindsight(symbol, provider_symbol):
    series = _make_series(provider_symbol)
    buy_date = _find_date(series, StrategyDecision.BUY, min_future_bars=10)
    deps = _deps_for(series, symbol)

    result = audit_strategy_decision(
        {
            "symbol": symbol,
            "audit_date": buy_date.isoformat(),
            "start": series.bars[0].date.isoformat(),
            "end": series.bars[-1].date.isoformat(),
        },
        deps,
    )

    assert result.status == "ok"
    assert result.data["decision"] == "BUY"
    hindsight = result.data["retrospective_hindsight"]
    assert hindsight["forward_return_10d"] is not None
    assert hindsight["available_forward_bars"] is not None
    assert hindsight["available_forward_bars"] >= 10


# ---------------------------------------------------------------------------
# Case B: BUY + < 10 future bars -> unavailable, with the correct reason
# (a number less than 10, decision still BUY -- distinct from case C/D)
# ---------------------------------------------------------------------------


def test_case_b_buy_near_end_of_range_reports_insufficient_forward_bars_not_a_missing_buy():
    series = _make_series(f"{_SYMBOL_A}.NS")
    buy_date = _find_date(series, StrategyDecision.BUY, min_future_bars=1)
    # Truncate the requested range to end just a few bars after the BUY
    # signal -- this is exactly how a real "audit near the data end"
    # request looks; nothing about the fixture is hand-tuned beyond that.
    truncated_end = buy_date + timedelta(days=4)
    deps = _deps_for(series, _SYMBOL_A)

    result = audit_strategy_decision(
        {
            "symbol": _SYMBOL_A,
            "audit_date": buy_date.isoformat(),
            "start": series.bars[0].date.isoformat(),
            "end": truncated_end.isoformat(),
        },
        deps,
    )

    assert result.status == "ok"
    assert result.data["decision"] == "BUY"
    hindsight = result.data["retrospective_hindsight"]
    assert hindsight["forward_return_10d"] is None
    assert hindsight["available_forward_bars"] is not None
    assert hindsight["available_forward_bars"] < 10


# ---------------------------------------------------------------------------
# Case C: NO_SIGNAL + future bars -> no BUY retrospective outcome, and the
# reason is unambiguously "not a BUY" (available_forward_bars is None too)
# ---------------------------------------------------------------------------


def test_case_c_no_signal_has_no_retrospective_outcome_and_no_forward_bar_count():
    series = _make_series(f"{_SYMBOL_B}.NS")
    no_signal_date = _find_date(series, StrategyDecision.NO_SIGNAL, min_future_bars=15)
    deps = _deps_for(series, _SYMBOL_B)

    result = audit_strategy_decision(
        {
            "symbol": _SYMBOL_B,
            "audit_date": no_signal_date.isoformat(),
            "start": series.bars[0].date.isoformat(),
            "end": series.bars[-1].date.isoformat(),
        },
        deps,
    )

    assert result.status == "ok"
    assert result.data["decision"] == "NO_SIGNAL"
    hindsight = result.data["retrospective_hindsight"]
    assert hindsight["forward_return_10d"] is None
    assert hindsight["available_forward_bars"] is None


# ---------------------------------------------------------------------------
# Case D: INSUFFICIENT_DATA -> same unambiguous "not a BUY" shape
# ---------------------------------------------------------------------------


def test_case_d_insufficient_data_has_no_retrospective_outcome_and_no_forward_bar_count():
    series = _make_series(f"{_SYMBOL_A}.NS")
    insufficient_date = _find_date(series, StrategyDecision.INSUFFICIENT_DATA, min_future_bars=15)
    deps = _deps_for(series, _SYMBOL_A)

    result = audit_strategy_decision(
        {
            "symbol": _SYMBOL_A,
            "audit_date": insufficient_date.isoformat(),
            "start": series.bars[0].date.isoformat(),
            "end": series.bars[-1].date.isoformat(),
        },
        deps,
    )

    assert result.status == "ok"
    assert result.data["decision"] == "INSUFFICIENT_DATA"
    hindsight = result.data["retrospective_hindsight"]
    assert hindsight["forward_return_10d"] is None
    assert hindsight["available_forward_bars"] is None


# ---------------------------------------------------------------------------
# Case E: symbol normalization does not break outcome lookup -- the exact
# same underlying close pattern, indexed under two DIFFERENT provider
# symbols, produces the identical decision/hindsight shape at the same
# relative date. The domain outcome lookup is keyed by date only (never by
# symbol string), so this also serves as a structural proof of that.
# ---------------------------------------------------------------------------


def test_case_e_symbol_normalization_does_not_change_outcome_lookup():
    series_a = _make_series(f"{_SYMBOL_A}.NS")
    series_b = _make_series(f"{_SYMBOL_B}.NS")
    buy_date_a = _find_date(series_a, StrategyDecision.BUY, min_future_bars=10)
    buy_date_b = _find_date(series_b, StrategyDecision.BUY, min_future_bars=10)
    assert buy_date_a == buy_date_b  # identical close pattern -> identical signal dates

    result_a = audit_strategy_decision(
        {
            "symbol": _SYMBOL_A,
            "audit_date": buy_date_a.isoformat(),
            "start": series_a.bars[0].date.isoformat(),
            "end": series_a.bars[-1].date.isoformat(),
        },
        _deps_for(series_a, _SYMBOL_A),
    )
    result_b = audit_strategy_decision(
        {
            "symbol": _SYMBOL_B,
            "audit_date": buy_date_b.isoformat(),
            "start": series_b.bars[0].date.isoformat(),
            "end": series_b.bars[-1].date.isoformat(),
        },
        _deps_for(series_b, _SYMBOL_B),
    )

    assert result_a.data["symbol"] == f"{_SYMBOL_A}.NS"
    assert result_b.data["symbol"] == f"{_SYMBOL_B}.NS"
    assert result_a.data["decision"] == result_b.data["decision"] == "BUY"
    assert (
        result_a.data["retrospective_hindsight"]["forward_return_10d"]
        == result_b.data["retrospective_hindsight"]["forward_return_10d"]
    )


# ---------------------------------------------------------------------------
# Case F: audit-date normalization does not break outcome lookup -- an
# ISO date string maps to the exact same bar as the domain `date` object
# it represents, with no off-by-one/timezone drift.
# ---------------------------------------------------------------------------


def test_case_f_audit_date_string_matches_the_exact_domain_bar_date():
    series = _make_series(f"{_SYMBOL_A}.NS")
    buy_date = _find_date(series, StrategyDecision.BUY, min_future_bars=10)
    deps = _deps_for(series, _SYMBOL_A)

    result = audit_strategy_decision(
        {
            "symbol": _SYMBOL_A,
            "audit_date": buy_date.isoformat(),
            "start": series.bars[0].date.isoformat(),
            "end": series.bars[-1].date.isoformat(),
        },
        deps,
    )
    assert result.status == "ok"
    assert result.data["audit_date"] == buy_date.isoformat()

    # Independently rebuild the outcome via the real domain engines and
    # confirm the exact same date-keyed lookup the tool performed.
    indicators = compute_indicators(series)
    evaluations = evaluate_strategy(series, indicators)
    outcomes = compute_signal_outcomes(series, evaluations)
    outcome_by_date = {o.date: o for o in outcomes.outcomes}
    assert buy_date in outcome_by_date
    assert result.data["retrospective_hindsight"]["forward_return_10d"] == outcome_by_date[buy_date].forward_return_10d
