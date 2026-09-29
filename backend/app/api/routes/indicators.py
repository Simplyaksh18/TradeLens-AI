"""Indicator values for a symbol/range. Exactly one market-data fetch per
request; all indicator math happens in app.indicators.engine, not here."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import HistoryQueryParams, get_market_data_service, history_query_params
from app.api.schemas.indicators import IndicatorResponse
from app.indicators.engine import compute_indicators
from app.market_data.service import MarketDataService

router = APIRouter()


@router.get(
    "/indicators/{symbol}",
    response_model=IndicatorResponse,
    summary="SMA20/SMA50/RSI14/rolling average volume/volume ratio for a symbol/range",
)
def get_indicators(
    symbol: str,
    params: HistoryQueryParams = Depends(history_query_params),
    service: MarketDataService = Depends(get_market_data_service),
) -> IndicatorResponse:
    market_series = service.get_history(symbol, params.interval, params.start, params.end)
    indicator_series = compute_indicators(market_series)
    return IndicatorResponse.from_domain(indicator_series)
