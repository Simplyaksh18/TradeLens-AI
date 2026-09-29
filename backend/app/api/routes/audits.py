"""Phase 3C point-in-time strategy audit for a symbol/range/audit_date.
Reuses the same market-data -> indicators -> strategy chain as /strategies
(see app.api.research), then the accepted Phase 2A outcomes engine and the
accepted Phase 3C composition engine. No audit calculation happens here --
this route only validates `audit_date`, separates calculation history from
the requested evidence window, and adapts the domain result to a response
schema. Never routes through Phase 2B backtesting or Phase 2C analytics --
this audits signals, not portfolio execution.

CALCULATION HISTORY vs HISTORICAL EVIDENCE WINDOW (Phase 3D correction --
see CLAUDE.md Phase 3D): the requested `start` is the lower bound of the
"Prior Strategy Signals" evidence population (`historical_evidence`/
`historical_signal_risk` only include signals with `signal_date >=
start`) -- it must NOT also starve SMA20/SMA50/RSI14/20-bar-volatility
warm-up for evaluating `audit_date` itself. So the market-data fetch uses
an internal `calc_start` that may reach further back than the requested
`start` (see `CALCULATION_WARMUP_CALENDAR_DAYS` below), while
`evidence_start_date=params.start` (the user's ORIGINAL requested start,
never `calc_start`) is passed to `build_strategy_audit` so extra warm-up
bars can never leak into the evidence population. `evaluation` and
`risk_market_context` are therefore independent of the requested `start`
(as long as `calc_start` reaches far enough back) -- only
`historical_evidence`/`historical_signal_risk` legitimately vary with it."""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta

from fastapi import APIRouter, Depends, Query

from app.api.dependencies import HistoryQueryParams, get_market_data_service, history_query_params
from app.api.errors import RequestContractError
from app.api.research import build_strategy_research
from app.api.schemas.audits import StrategyAuditResponse
from app.audit.engine import build_strategy_audit
from app.market_data.service import MarketDataService
from app.outcomes.engine import compute_signal_outcomes

router = APIRouter()

# Comfortably covers the accepted 50-TRADING-bar SMA50 warm-up (~70 trading
# days -> well under 120 calendar days even accounting for NSE weekends/
# holidays), plus RSI14/20-bar-volatility's smaller windows. A calendar-day
# margin is used because the market-data service's fetch contract is
# date-range-based, not trading-bar-count-based -- there is no cleaner
# existing primitive to request "N trading bars back" directly (see
# app.market_data.service.MarketDataService.get_history). If the provider
# genuinely lacks 50 trading bars even within this widened window (e.g. a
# newly listed instrument), the strategy/indicator engines still correctly
# fall back to their existing INSUFFICIENT_DATA state -- this constant
# only removes the ARTIFICIAL starvation caused by a too-tight requested
# `start`, it does not change what "sufficient history" means.
CALCULATION_WARMUP_CALENDAR_DAYS = 120


@router.get(
    "/audits/trend-momentum-v1/{symbol}",
    response_model=StrategyAuditResponse,
    summary="Phase 3C point-in-time strategy audit for a symbol/range/audit_date",
)
def get_trend_momentum_v1_audit(
    symbol: str,
    audit_date: Date = Query(
        ...,
        description=(
            "Exact trading-bar date being audited (YYYY-MM-DD). Must fall within "
            "[start, end] and correspond exactly to a trading bar -- never silently "
            "remapped to the nearest trading day."
        ),
    ),
    params: HistoryQueryParams = Depends(history_query_params),
    service: MarketDataService = Depends(get_market_data_service),
) -> StrategyAuditResponse:
    calc_start = min(params.start, audit_date - timedelta(days=CALCULATION_WARMUP_CALENDAR_DAYS))
    calc_params = HistoryQueryParams(start=calc_start, end=params.end, interval=params.interval)
    market_series, indicator_series, evaluation_series = build_strategy_research(symbol, calc_params, service)

    # Validated here (stable 422), not left to the domain layer's internal-
    # contract exception (500) -- a user picking a weekend/holiday or an
    # out-of-range date is an ordinary request mistake, not an internal
    # data-integrity failure. The response's audit_date always equals the
    # requested audit_date; it is never silently substituted.
    if not any(bar.date == audit_date for bar in market_series.bars):
        raise RequestContractError(
            "AUDIT_DATE_NOT_A_TRADING_BAR",
            f"No trading bar exists for audit_date {audit_date} within the available data through the requested range.",
        )

    outcome_series = compute_signal_outcomes(market_series, evaluation_series)
    audit = build_strategy_audit(
        market_series, evaluation_series, outcome_series, indicator_series, audit_date,
        evidence_start_date=params.start,  # the user's ORIGINAL requested start, never calc_start
    )
    return StrategyAuditResponse.from_domain(audit)
