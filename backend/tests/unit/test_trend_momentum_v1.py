from datetime import date

import pytest

from app.core.exceptions import StrategyInputInvalidError
from app.strategies.models import StrategyDecision
from app.strategies.trend_momentum_v1 import STRATEGY_ID, STRATEGY_NAME, evaluate_trend_momentum_v1

D = date(2024, 1, 1)


def _evaluate(close=120.0, sma20=110.0, sma50=100.0, rsi14=55.0):
    return evaluate_trend_momentum_v1(D, close=close, sma20=sma20, sma50=sma50, rsi14=rsi14)


# ---------------------------------------------------------------------------
# BUY
# ---------------------------------------------------------------------------


def test_buy_when_all_three_conditions_pass():
    result = _evaluate(close=120, sma20=110, sma50=100, rsi14=55)

    assert result.decision is StrategyDecision.BUY
    assert result.missing_inputs == ()
    assert result.strategy_id == STRATEGY_ID
    assert result.strategy_name == STRATEGY_NAME
    assert len(result.conditions) == 3

    by_id = {c.condition_id: c for c in result.conditions}
    assert by_id["close_above_sma20"].passed is True
    assert by_id["sma20_above_sma50"].passed is True
    assert by_id["rsi_in_range"].passed is True

    close_condition = by_id["close_above_sma20"]
    assert close_condition.operator == ">"
    values = {v.name: v.value for v in close_condition.actual_values}
    assert values == {"close": 120.0, "sma20": 110.0}


# ---------------------------------------------------------------------------
# Individual NO_SIGNAL cases
# ---------------------------------------------------------------------------


def test_no_signal_close_below_sma20():
    result = _evaluate(close=105, sma20=110, sma50=100, rsi14=55)  # close < sma20
    assert result.decision is StrategyDecision.NO_SIGNAL
    by_id = {c.condition_id: c for c in result.conditions}
    assert by_id["close_above_sma20"].passed is False
    assert by_id["sma20_above_sma50"].passed is True
    assert by_id["rsi_in_range"].passed is True
    assert len(result.conditions) == 3


def test_no_signal_sma_trend_failure():
    result = _evaluate(close=120, sma20=95, sma50=100, rsi14=55)  # sma20 < sma50
    assert result.decision is StrategyDecision.NO_SIGNAL
    by_id = {c.condition_id: c for c in result.conditions}
    assert by_id["sma20_above_sma50"].passed is False


def test_no_signal_rsi_below_40():
    result = _evaluate(close=120, sma20=110, sma50=100, rsi14=39.9)
    assert result.decision is StrategyDecision.NO_SIGNAL
    by_id = {c.condition_id: c for c in result.conditions}
    assert by_id["rsi_in_range"].passed is False


def test_no_signal_rsi_above_70():
    result = _evaluate(close=120, sma20=110, sma50=100, rsi14=70.1)
    assert result.decision is StrategyDecision.NO_SIGNAL
    by_id = {c.condition_id: c for c in result.conditions}
    assert by_id["rsi_in_range"].passed is False


# ---------------------------------------------------------------------------
# Exact boundary semantics (no epsilon)
# ---------------------------------------------------------------------------


def test_close_equal_sma20_fails():
    result = _evaluate(close=110.0, sma20=110.0, sma50=100.0, rsi14=55.0)
    by_id = {c.condition_id: c for c in result.conditions}
    assert by_id["close_above_sma20"].passed is False
    assert result.decision is StrategyDecision.NO_SIGNAL


def test_sma20_equal_sma50_fails():
    result = _evaluate(close=120.0, sma20=100.0, sma50=100.0, rsi14=55.0)
    by_id = {c.condition_id: c for c in result.conditions}
    assert by_id["sma20_above_sma50"].passed is False
    assert result.decision is StrategyDecision.NO_SIGNAL


@pytest.mark.parametrize(
    "rsi_value, expected_pass",
    [
        (39.999, False),
        (40.000, True),
        (70.000, True),
        (70.001, False),
    ],
)
def test_rsi_inclusive_boundaries(rsi_value, expected_pass):
    result = _evaluate(close=120, sma20=110, sma50=100, rsi14=rsi_value)
    by_id = {c.condition_id: c for c in result.conditions}
    assert by_id["rsi_in_range"].passed is expected_pass


# ---------------------------------------------------------------------------
# Multiple simultaneous failures
# ---------------------------------------------------------------------------


def test_multiple_failures_all_three_conditions_still_reported():
    result = _evaluate(close=90, sma20=95, sma50=100, rsi14=75)  # close<sma20, sma20<sma50, rsi>70
    assert result.decision is StrategyDecision.NO_SIGNAL
    assert len(result.conditions) == 3
    assert all(c.passed is False for c in result.conditions)
    assert [c.condition_id for c in result.conditions] == [
        "close_above_sma20", "sma20_above_sma50", "rsi_in_range",
    ]


# ---------------------------------------------------------------------------
# INSUFFICIENT_DATA
# ---------------------------------------------------------------------------


def test_insufficient_data_all_indicators_missing():
    result = evaluate_trend_momentum_v1(D, close=125.0, sma20=None, sma50=None, rsi14=None)
    assert result.decision is StrategyDecision.INSUFFICIENT_DATA
    assert result.missing_inputs == ("sma20", "sma50", "rsi14")
    assert result.conditions == ()


def test_insufficient_data_only_sma50_missing():
    result = evaluate_trend_momentum_v1(D, close=125.0, sma20=120.0, sma50=None, rsi14=55.0)
    assert result.decision is StrategyDecision.INSUFFICIENT_DATA
    assert result.missing_inputs == ("sma50",)
    assert result.conditions == ()


def test_insufficient_data_close_missing_conceptually():
    # close is always present from validated market data in practice, but
    # the contract must remain explicit per Phase 1D spec section 5.
    result = evaluate_trend_momentum_v1(D, close=None, sma20=120.0, sma50=110.0, rsi14=55.0)
    assert result.decision is StrategyDecision.INSUFFICIENT_DATA
    assert result.missing_inputs == ("close",)
    assert result.conditions == ()


def test_insufficient_data_does_not_partially_evaluate():
    # sma20/rsi14 would both PASS if evaluated, but sma50 is missing, so no
    # condition evaluation may occur at all.
    result = evaluate_trend_momentum_v1(D, close=125.0, sma20=120.0, sma50=None, rsi14=55.0)
    assert result.conditions == ()


# ---------------------------------------------------------------------------
# Malformed numeric input (structural failure, not NO_SIGNAL/INSUFFICIENT_DATA)
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(sma20=float("nan")),
        dict(sma50=float("inf")),
        dict(rsi14=float("-inf")),
        dict(rsi14=101.0),
        dict(rsi14=-1.0),
        dict(close=float("nan")),
    ],
)
def test_malformed_numeric_input_raises_explicitly(kwargs):
    base = dict(close=120.0, sma20=110.0, sma50=100.0, rsi14=55.0)
    base.update(kwargs)
    with pytest.raises(StrategyInputInvalidError):
        evaluate_trend_momentum_v1(D, **base)


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------


def test_deterministic_repeated_evaluation():
    r1 = _evaluate()
    r2 = _evaluate()
    assert r1 == r2
