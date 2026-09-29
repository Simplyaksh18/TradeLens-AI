"""Phase 2A historical BUY-signal outcomes for a symbol/range. Reuses the
same market-data -> indicators -> strategy chain as /strategies (see
app.api.research). No outcome calculation happens here -- this route only
adapts the accepted Phase 2A domain result to a response schema."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from app.api.dependencies import HistoryQueryParams, get_market_data_service, history_query_params
from app.api.research import build_strategy_research
from app.api.schemas.outcomes import SignalOutcomeSeriesResponse
from app.market_data.service import MarketDataService
from app.outcomes.engine import compute_signal_outcomes

router = APIRouter()


@router.get(
    "/outcomes/trend-momentum-v1/{symbol}",
    response_model=SignalOutcomeSeriesResponse,
    summary="Phase 2A historical BUY-signal outcomes for a symbol/range",
)
def get_trend_momentum_v1_outcomes(
    symbol: str,
    params: HistoryQueryParams = Depends(history_query_params),
    service: MarketDataService = Depends(get_market_data_service),
) -> SignalOutcomeSeriesResponse:
    market_series, _indicator_series, evaluation_series = build_strategy_research(symbol, params, service)
    outcome_series = compute_signal_outcomes(market_series, evaluation_series)
    return SignalOutcomeSeriesResponse.from_domain(outcome_series)
