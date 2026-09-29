"""Phase 1D series-level orchestration: structural alignment + evaluation.

Consumes already-normalized `OHLCVSeries` (Phase 1A) and already-calculated
`IndicatorSeries` (Phase 1C). Does not recalculate any indicator, does not
touch providers/cache/network, and does not reorder/repair/truncate either
input — a structural mismatch is an explicit failure, never silently fixed.
"""

from __future__ import annotations

from app.core.exceptions import StrategyInputInvalidError
from app.indicators.models import IndicatorSeries
from app.market_data.models import OHLCVSeries
from app.strategies.models import StrategyEvaluationSeries
from app.strategies.trend_momentum_v1 import STRATEGY_ID, STRATEGY_NAME, evaluate_trend_momentum_v1


def evaluate_strategy(market_series: OHLCVSeries, indicator_series: IndicatorSeries) -> StrategyEvaluationSeries:
    """Evaluate Trend + Momentum v1 for every date in the aligned input.

    Raises StrategyInputInvalidError if `market_series` and
    `indicator_series` are not structurally aligned (symbol, interval,
    length, or per-row date). Produces exactly one StrategyEvaluation per
    input row, including INSUFFICIENT_DATA rows for warm-up dates.
    """
    _validate_alignment(market_series, indicator_series)

    evaluations = tuple(
        evaluate_trend_momentum_v1(
            date=bar.date,
            close=bar.close,
            sma20=row.sma20,
            sma50=row.sma50,
            rsi14=row.rsi14,
        )
        for bar, row in zip(market_series.bars, indicator_series.rows)
    )

    return StrategyEvaluationSeries(
        provider_symbol=market_series.provider_symbol,
        interval=market_series.interval,
        strategy_id=STRATEGY_ID,
        strategy_name=STRATEGY_NAME,
        evaluations=evaluations,
    )


def _validate_alignment(market_series: OHLCVSeries, indicator_series: IndicatorSeries) -> None:
    if market_series.provider_symbol != indicator_series.provider_symbol:
        raise StrategyInputInvalidError(
            f"Symbol mismatch: market series {market_series.provider_symbol!r} vs "
            f"indicator series {indicator_series.provider_symbol!r}"
        )
    if market_series.interval != indicator_series.interval:
        raise StrategyInputInvalidError(
            f"Interval mismatch: market series {market_series.interval!r} vs "
            f"indicator series {indicator_series.interval!r}"
        )
    if len(market_series.bars) != len(indicator_series.rows):
        raise StrategyInputInvalidError(
            f"Row count mismatch: {len(market_series.bars)} market bars vs "
            f"{len(indicator_series.rows)} indicator rows"
        )
    for bar, row in zip(market_series.bars, indicator_series.rows):
        if bar.date != row.date:
            raise StrategyInputInvalidError(
                f"Date misalignment: market bar date {bar.date} != indicator row date {row.date}"
            )
