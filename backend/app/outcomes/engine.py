"""Phase 2A: deterministic historical signal outcome engine.

Consumes an already-computed Phase 1D `StrategyEvaluationSeries` and its
structurally aligned `OHLCVSeries`, and computes purely observational,
forward-looking research metrics for each BUY evaluation: the raw Close
+5 and +10 TRADING-BAR after the signal date, and the maximum adverse/
favorable price excursion over a full 10-trading-bar window.

Strict temporal separation (see CLAUDE.md Phase 2A): this module never
feeds information back into, or otherwise alters, the Phase 1D decision at
T — it only reads a decision Phase 1D has already produced and measures
what the market did strictly *after* T. It never recalculates whether a
row "should" have been BUY.

NO_SIGNAL and INSUFFICIENT_DATA evaluations produce no SignalOutcome — they
are not entries. Consecutive BUY evaluations are NOT collapsed here; each
qualifying historical BUY produces its own independent SignalOutcome
(entry-event/position deduplication is a Phase 2B concern).

This is Phase 2A only — NOT the Phase 2B portfolio backtester. It never
answers "could we execute", "how many shares", "what about fees/slippage",
or "when does the position exit".
"""

from __future__ import annotations

from datetime import date as Date
from math import isfinite

from app.core.exceptions import OutcomeInputInvalidError
from app.market_data.models import OHLCVBar, OHLCVSeries
from app.outcomes.models import SignalOutcome, SignalOutcomeSeries
from app.strategies.models import StrategyDecision, StrategyEvaluationSeries

FORWARD_5D_BARS = 5
FORWARD_10D_BARS = 10


def compute_signal_outcomes(
    market_series: OHLCVSeries, evaluation_series: StrategyEvaluationSeries
) -> SignalOutcomeSeries:
    """Compute Phase 2A outcomes for every BUY evaluation in the series.

    Raises OutcomeInputInvalidError if `market_series` and
    `evaluation_series` are not structurally aligned (symbol, interval,
    length, or per-row date), or if a required OHLC value used in a
    calculation is non-finite.
    """
    _validate_alignment(market_series, evaluation_series)

    bars = market_series.bars
    outcomes = tuple(
        _compute_single_outcome(bars, i, evaluation.date)
        for i, evaluation in enumerate(evaluation_series.evaluations)
        if evaluation.decision == StrategyDecision.BUY
    )

    return SignalOutcomeSeries(
        provider_symbol=market_series.provider_symbol,
        interval=market_series.interval,
        strategy_id=evaluation_series.strategy_id,
        strategy_name=evaluation_series.strategy_name,
        outcomes=outcomes,
    )


def _require_finite(value: float, context: str) -> float:
    if not isfinite(value):
        raise OutcomeInputInvalidError(f"Non-finite value encountered while computing outcome: {context}")
    return value


def _compute_single_outcome(bars: tuple[OHLCVBar, ...], i: int, signal_date: Date) -> SignalOutcome:
    n = len(bars)
    reference_close = _require_finite(bars[i].close, f"reference close at {signal_date}")

    forward_close_5d = None
    forward_return_5d = None
    if i + FORWARD_5D_BARS < n:
        forward_close_5d = _require_finite(bars[i + FORWARD_5D_BARS].close, f"+5D close after {signal_date}")
        forward_return_5d = forward_close_5d / reference_close - 1

    forward_close_10d = None
    forward_return_10d = None
    if i + FORWARD_10D_BARS < n:
        forward_close_10d = _require_finite(bars[i + FORWARD_10D_BARS].close, f"+10D close after {signal_date}")
        forward_return_10d = forward_close_10d / reference_close - 1

    # Signal bar itself is excluded from the excursion window (see
    # CLAUDE.md Phase 2A). A full 10-bar window is required for either
    # metric — a partial window is never presented as a full 10D measurement.
    window = bars[i + 1 : i + 1 + FORWARD_10D_BARS]
    mae_10d = None
    mfe_10d = None
    if len(window) == FORWARD_10D_BARS:
        lows = [_require_finite(b.low, f"future low after {signal_date}") for b in window]
        highs = [_require_finite(b.high, f"future high after {signal_date}") for b in window]
        mae_10d = min(lows) / reference_close - 1
        mfe_10d = max(highs) / reference_close - 1

    return SignalOutcome(
        date=signal_date,
        decision=StrategyDecision.BUY,
        reference_close=reference_close,
        forward_close_5d=forward_close_5d,
        forward_return_5d=forward_return_5d,
        forward_close_10d=forward_close_10d,
        forward_return_10d=forward_return_10d,
        mae_10d=mae_10d,
        mfe_10d=mfe_10d,
        available_forward_bars=n - 1 - i,
    )


def _validate_alignment(market_series: OHLCVSeries, evaluation_series: StrategyEvaluationSeries) -> None:
    if market_series.provider_symbol != evaluation_series.provider_symbol:
        raise OutcomeInputInvalidError(
            f"Symbol mismatch: market series {market_series.provider_symbol!r} vs "
            f"evaluation series {evaluation_series.provider_symbol!r}"
        )
    if market_series.interval != evaluation_series.interval:
        raise OutcomeInputInvalidError(
            f"Interval mismatch: market series {market_series.interval!r} vs "
            f"evaluation series {evaluation_series.interval!r}"
        )
    if len(market_series.bars) != len(evaluation_series.evaluations):
        raise OutcomeInputInvalidError(
            f"Row count mismatch: {len(market_series.bars)} market bars vs "
            f"{len(evaluation_series.evaluations)} evaluations"
        )
    for bar, evaluation in zip(market_series.bars, evaluation_series.evaluations):
        if bar.date != evaluation.date:
            raise OutcomeInputInvalidError(f"Date misalignment: market bar date {bar.date} != evaluation date {evaluation.date}")
