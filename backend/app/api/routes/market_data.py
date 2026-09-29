"""Historical normalized OHLCV bars. No calculation logic lives here — this
route only calls MarketDataService.get_history and maps its result."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import HistoryQueryParams, get_market_data_service, history_query_params
from app.api.schemas.market_data import MarketDataResponse
from app.market_data.service import MarketDataService

router = APIRouter()


@router.get(
    "/market-data/{symbol}",
    response_model=MarketDataResponse,
    summary="Historical normalized OHLCV bars (raw close and adj_close kept distinct)",
)
def get_market_data(
    symbol: str,
    params: HistoryQueryParams = Depends(history_query_params),
    service: MarketDataService = Depends(get_market_data_service),
) -> MarketDataResponse:
    series = service.get_history(symbol, params.interval, params.start, params.end)
    return MarketDataResponse.from_domain(series)
