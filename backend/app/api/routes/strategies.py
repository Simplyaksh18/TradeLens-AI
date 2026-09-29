"""Trend + Momentum v1 strategy evaluation for a symbol/range. Exactly one
market-data fetch per request, reused for both indicator calculation and
strategy evaluation. No strategy logic lives here."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import HistoryQueryParams, get_market_data_service, history_query_params
from app.api.research import build_strategy_research
from app.api.schemas.strategies import StrategyEvaluationSeriesResponse
from app.market_data.service import MarketDataService

router = APIRouter()


@router.get(
    "/strategies/trend-momentum-v1/{symbol}",
    response_model=StrategyEvaluationSeriesResponse,
    summary="Trend + Momentum v1 strategy evaluation for a symbol/range",
)
def get_trend_momentum_v1(
    symbol: str,
    params: HistoryQueryParams = Depends(history_query_params),
    service: MarketDataService = Depends(get_market_data_service),
) -> StrategyEvaluationSeriesResponse:
    _market_series, _indicator_series, evaluation_series = build_strategy_research(symbol, params, service)
    return StrategyEvaluationSeriesResponse.from_domain(evaluation_series)
