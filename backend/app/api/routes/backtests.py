"""Phase 2B executable backtest for a symbol/range. Reuses the same
market-data -> indicators -> strategy chain as /strategies (see
app.api.research). No execution/P&L calculation happens here -- this route
only adapts the accepted Phase 2B domain result to a response schema. No
Phase 2C analytics are computed on this route."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import (
    BacktestQueryParams,
    HistoryQueryParams,
    backtest_query_params,
    get_market_data_service,
    history_query_params,
)
from app.api.research import build_strategy_research
from app.api.schemas.backtests import BacktestResultResponse
from app.backtesting.engine import run_backtest
from app.backtesting.models import BacktestConfig
from app.market_data.service import MarketDataService

router = APIRouter()


@router.get(
    "/backtests/trend-momentum-v1/{symbol}",
    response_model=BacktestResultResponse,
    summary="Phase 2B executable backtest for a symbol/range",
)
def get_trend_momentum_v1_backtest(
    symbol: str,
    params: HistoryQueryParams = Depends(history_query_params),
    capital_params: BacktestQueryParams = Depends(backtest_query_params),
    service: MarketDataService = Depends(get_market_data_service),
) -> BacktestResultResponse:
    market_series, _indicator_series, evaluation_series = build_strategy_research(symbol, params, service)
    config = BacktestConfig(initial_capital=capital_params.initial_capital)
    result = run_backtest(market_series, evaluation_series, config)
    return BacktestResultResponse.from_domain(result)
