"""Trend + Momentum v1 — pure single-row deterministic strategy rule.

BUY only when ALL of:
  C1 close_above_sma20: close > sma20   (strict; close == sma20 -> FAIL)
  C2 sma20_above_sma50: sma20 > sma50   (strict; sma20 == sma50 -> FAIL)
  C3 rsi_in_range:      40.0 <= rsi14 <= 70.0 (inclusive both ends, no epsilon)

No volume, no crossover/slope/persistence filters, no exit/SELL semantics —
this strategy evaluates each date's state independently.

Not aware of providers, caching, FastAPI, backtesting, future bars, or
portfolio state — a pure function of the 4 required scalar inputs.
"""

from __future__ import annotations

import math
from typing import Optional

from app.core.exceptions import StrategyInputInvalidError
from app.strategies.models import ConditionResult, NamedValue, StrategyDecision, StrategyEvaluation

STRATEGY_ID = "trend_momentum_v1"
STRATEGY_NAME = "Trend + Momentum v1"

RSI_LOWER_BOUND = 40.0
RSI_UPPER_BOUND = 70.0

# Canonical order for both missing-input reporting and condition evaluation.
_REQUIRED_INPUTS = ("close", "sma20", "sma50", "rsi14")


def evaluate_trend_momentum_v1(
    date,
    close: Optional[float],
    sma20: Optional[float],
    sma50: Optional[float],
    rsi14: Optional[float],
) -> StrategyEvaluation:
    """Evaluate the Trend + Momentum v1 rule for a single trading date.

    `close` must be the RAW close (never `adj_close`) for the same date as
    `sma20`/`sma50`/`rsi14` — alignment itself is the caller's (engine.py)
    responsibility, not this function's.

    Raises StrategyInputInvalidError for structurally invalid present values
    (non-finite, or RSI outside [0, 100]) — never for `None`, which is the
    legitimate INSUFFICIENT_DATA case.
    """
    values = {"close": close, "sma20": sma20, "sma50": sma50, "rsi14": rsi14}
    missing = tuple(name for name in _REQUIRED_INPUTS if values[name] is None)

    if missing:
        return StrategyEvaluation(
            date=date,
            strategy_id=STRATEGY_ID,
            strategy_name=STRATEGY_NAME,
            decision=StrategyDecision.INSUFFICIENT_DATA,
            conditions=(),
            missing_inputs=missing,
        )

    for name in _REQUIRED_INPUTS:
        _require_finite(name, values[name])
    _require_valid_rsi_domain(rsi14)

    conditions = (
        _evaluate_close_above_sma20(close, sma20),
        _evaluate_sma20_above_sma50(sma20, sma50),
        _evaluate_rsi_in_range(rsi14),
    )
    decision = StrategyDecision.BUY if all(c.passed for c in conditions) else StrategyDecision.NO_SIGNAL

    return StrategyEvaluation(
        date=date,
        strategy_id=STRATEGY_ID,
        strategy_name=STRATEGY_NAME,
        decision=decision,
        conditions=conditions,
        missing_inputs=(),
    )


def _require_finite(name: str, value: float) -> None:
    if not math.isfinite(value):
        raise StrategyInputInvalidError(f"Strategy input {name!r} is not finite: {value!r}")


def _require_valid_rsi_domain(rsi14: float) -> None:
    if not (0.0 <= rsi14 <= 100.0):
        raise StrategyInputInvalidError(
            f"rsi14 is outside its mathematical domain [0, 100]: {rsi14!r}"
        )


def _evaluate_close_above_sma20(close: float, sma20: float) -> ConditionResult:
    return ConditionResult(
        condition_id="close_above_sma20",
        description="Close is above SMA20",
        passed=close > sma20,
        actual_values=(NamedValue("close", close), NamedValue("sma20", sma20)),
        operator=">",
        reference_values=(),
    )


def _evaluate_sma20_above_sma50(sma20: float, sma50: float) -> ConditionResult:
    return ConditionResult(
        condition_id="sma20_above_sma50",
        description="SMA20 is above SMA50",
        passed=sma20 > sma50,
        actual_values=(NamedValue("sma20", sma20), NamedValue("sma50", sma50)),
        operator=">",
        reference_values=(),
    )


def _evaluate_rsi_in_range(rsi14: float) -> ConditionResult:
    return ConditionResult(
        condition_id="rsi_in_range",
        description="RSI14 is within the inclusive strategy range",
        passed=RSI_LOWER_BOUND <= rsi14 <= RSI_UPPER_BOUND,
        actual_values=(NamedValue("rsi14", rsi14),),
        operator="inclusive_range",
        reference_values=(
            NamedValue("lower_bound", RSI_LOWER_BOUND),
            NamedValue("upper_bound", RSI_UPPER_BOUND),
        ),
    )
