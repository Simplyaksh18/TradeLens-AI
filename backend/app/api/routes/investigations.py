"""Phase 4E: Strategy Failure Investigation exposed over HTTP.

Pure adapter over the accepted Phase 2A/4A/4B/4C/4D domain layer -- no
classification, population arithmetic, mean/median, MAE/MFE, RSI, SMA,
volatility, regime, or trend-distance calculation happens here. This
route only orchestrates ONE market-data fetch, separates calculation
history from the requested investigation window (see below), and adapts
the composed Phase 4D result to a response schema.

CALCULATION HISTORY vs INVESTIGATION WINDOW (same lesson as Phase 3D --
see CLAUDE.md Phase 3D and Phase 4E): the requested `start` is the lower
bound of the INVESTIGATION POPULATION (which historical BUY signals are
included) -- it must NOT also starve SMA20/SMA50/RSI14/20-bar-volatility
warm-up for signals near `start`. So the market-data fetch uses an
internal `calc_start` that reaches further back than the requested
`start` (reusing the same `CALCULATION_WARMUP_CALENDAR_DAYS` constant
already established by the Phase 3D `/audits` route -- imported, not
redefined, so the two routes can never silently drift apart), while the
Phase 2A outcome series computed over that full calculation window is
then FILTERED to `start <= signal_date <= end` before it ever reaches
Phase 4A. This filtering is pure selection (no field of any `SignalOutcome`
is touched) -- warm-up-only signals before `start` can never leak into
the investigation population, exactly mirroring the Phase 3D correction.

`end` is the data/research end boundary only -- it is never extended to
manufacture a complete forward outcome. A signal near `end` with fewer
than 10 forward trading bars remains UNAVAILABLE per the accepted Phase
2A/4A censoring rules, and is never silently dropped from the response.
"""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends

from app.api.dependencies import HistoryQueryParams, get_market_data_service, history_query_params
from app.api.research import build_strategy_research
from app.api.routes.audits import CALCULATION_WARMUP_CALENDAR_DAYS
from app.api.schemas.investigations import StrategyFailureInvestigationResponse
from app.investigation.comparison import build_failure_population_comparison
from app.investigation.composer import build_strategy_failure_investigation
from app.investigation.context import build_failure_context_dataset
from app.investigation.engine import build_signal_investigation_dataset
from app.market_data.service import MarketDataService
from app.outcomes.engine import compute_signal_outcomes
from app.outcomes.models import SignalOutcomeSeries

router = APIRouter()


@router.get(
    "/investigations/trend-momentum-v1/{symbol}",
    response_model=StrategyFailureInvestigationResponse,
    summary="Phase 4D Strategy Failure Investigation for a symbol/range",
)
def get_trend_momentum_v1_investigation(
    symbol: str,
    params: HistoryQueryParams = Depends(history_query_params),
    service: MarketDataService = Depends(get_market_data_service),
) -> StrategyFailureInvestigationResponse:
    calc_start = params.start - timedelta(days=CALCULATION_WARMUP_CALENDAR_DAYS)
    calc_params = HistoryQueryParams(start=calc_start, end=params.end, interval=params.interval)
    market_series, indicator_series, evaluation_series = build_strategy_research(symbol, calc_params, service)

    outcome_series = compute_signal_outcomes(market_series, evaluation_series)
    windowed_outcome_series = _restrict_to_window(outcome_series, params.start, params.end)

    investigation_dataset = build_signal_investigation_dataset(windowed_outcome_series)
    outcome_comparison = build_failure_population_comparison(investigation_dataset)
    # The FULL calc-range market/indicator series is reused here (not
    # re-sliced to [start, end]) so a signal exactly at `start` still has
    # its complete SMA50/RSI14/20-bar-volatility warm-up history available
    # -- see the module docstring.
    context_analysis = build_failure_context_dataset(investigation_dataset, market_series, indicator_series)
    investigation = build_strategy_failure_investigation(investigation_dataset, outcome_comparison, context_analysis)

    return StrategyFailureInvestigationResponse.from_domain(investigation)


def _restrict_to_window(outcome_series: SignalOutcomeSeries, start, end) -> SignalOutcomeSeries:
    """Restricts the INVESTIGATION POPULATION to signals with
    `start <= signal_date <= end` (both inclusive). Pure filtering -- every
    `SignalOutcome` field (including forward returns computed using bars
    beyond the requested `end`... which never happens, since the market
    fetch itself never reaches past `end`) is preserved exactly. Order is
    preserved (Phase 2A already produces `outcomes` in chronological
    order)."""
    windowed = tuple(o for o in outcome_series.outcomes if start <= o.date <= end)
    return SignalOutcomeSeries(
        provider_symbol=outcome_series.provider_symbol,
        interval=outcome_series.interval,
        strategy_id=outcome_series.strategy_id,
        strategy_name=outcome_series.strategy_name,
        outcomes=windowed,
    )
