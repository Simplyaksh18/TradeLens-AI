"""Shared Phase 2D route orchestration.

The market-data-fetch -> indicators -> strategy-evaluation chain is
identical across the strategies, outcomes, backtests, and analytics
routes. This is the ONLY place that sequence is assembled, so each route
stays a thin adapter and none of them duplicate it independently.

Deliberately not a framework: one function, no new abstraction beyond
what's needed to avoid repeating three lines four times.
"""

from __future__ import annotations

from app.api.dependencies import HistoryQueryParams
from app.indicators.engine import compute_indicators
from app.indicators.models import IndicatorSeries
from app.market_data.models import OHLCVSeries
from app.market_data.service import MarketDataService
from app.strategies.engine import evaluate_strategy
from app.strategies.models import StrategyEvaluationSeries


def build_strategy_research(
    symbol: str, params: HistoryQueryParams, service: MarketDataService
) -> tuple[OHLCVSeries, IndicatorSeries, StrategyEvaluationSeries]:
    market_series = service.get_history(symbol, params.interval, params.start, params.end)
    indicator_series = compute_indicators(market_series)
    evaluation_series = evaluate_strategy(market_series, indicator_series)
    return market_series, indicator_series, evaluation_series
