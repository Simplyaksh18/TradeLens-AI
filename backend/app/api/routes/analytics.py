"""Phase 2C performance/risk analytics for a symbol/range. Runs the
accepted pipeline: market data -> indicators -> strategy -> Phase 2B
backtest -> Phase 2C analytics. No metric is calculated here -- this route
only adapts the accepted Phase 2C domain result to a response schema.

Phase 2B execution never consumes Phase 2A outcome metrics; this route
does not touch app.outcomes at all -- see app.api.research and
CLAUDE.md Phase 2D for the full dependency-direction note."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.analytics.engine import compute_performance_analytics
from app.api.dependencies import (
    BacktestQueryParams,
    HistoryQueryParams,
    backtest_query_params,
    get_market_data_service,
    history_query_params,
)
from app.api.research import build_strategy_research
from app.api.schemas.analytics import PerformanceAnalyticsResponse
from app.backtesting.engine import run_backtest
from app.backtesting.models import BacktestConfig
from app.market_data.service import MarketDataService

router = APIRouter()


@router.get(
    "/analytics/trend-momentum-v1/{symbol}",
    response_model=PerformanceAnalyticsResponse,
    summary="Phase 2C performance/risk analytics for a symbol/range",
)
def get_trend_momentum_v1_analytics(
    symbol: str,
    params: HistoryQueryParams = Depends(history_query_params),
    capital_params: BacktestQueryParams = Depends(backtest_query_params),
    service: MarketDataService = Depends(get_market_data_service),
) -> PerformanceAnalyticsResponse:
    market_series, _indicator_series, evaluation_series = build_strategy_research(symbol, params, service)
    config = BacktestConfig(initial_capital=capital_params.initial_capital)
    result = run_backtest(market_series, evaluation_series, config)
    analytics = compute_performance_analytics(result)
    return PerformanceAnalyticsResponse.from_domain(analytics, result)
