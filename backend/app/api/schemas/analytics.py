"""Phase 2C API representation.

Exposes exactly the accepted Phase 2C V1 `PerformanceAnalytics` fields --
no annualized volatility, CAGR, Sharpe/Sortino/Calmar, alpha/beta, or
benchmark comparison. `PerformanceAnalytics` itself carries no
symbol/strategy metadata, so `from_domain` also takes the source
`BacktestResult` to fill that in.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Optional

from pydantic import BaseModel

from app.analytics.models import DrawdownPoint, PerformanceAnalytics
from app.backtesting.models import BacktestResult


class DrawdownPointSchema(BaseModel):
    date: Date
    equity: float
    running_peak: float
    drawdown: float

    @classmethod
    def from_domain(cls, point: DrawdownPoint) -> "DrawdownPointSchema":
        return cls(date=point.date, equity=point.equity, running_peak=point.running_peak, drawdown=point.drawdown)


class PerformanceAnalyticsResponse(BaseModel):
    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str

    initial_equity: float
    ending_equity: float
    total_return: float

    realized_pnl: float
    unrealized_pnl: float
    total_pnl: float

    closed_trade_count: int
    winner_count: int
    loser_count: int
    breakeven_count: int
    win_rate: Optional[float]

    average_trade_return: Optional[float]
    median_trade_return: Optional[float]
    best_trade_return: Optional[float]
    worst_trade_return: Optional[float]

    peak_equity: float

    maximum_drawdown: float
    max_drawdown_peak_date: Date
    max_drawdown_trough_date: Date

    exposed_bar_count: int
    total_bar_count: int
    exposure: Optional[float]

    drawdown_series: list[DrawdownPointSchema]

    @classmethod
    def from_domain(cls, analytics: PerformanceAnalytics, result: BacktestResult) -> "PerformanceAnalyticsResponse":
        return cls(
            provider_symbol=result.provider_symbol,
            interval=result.interval,
            strategy_id=result.strategy_id,
            strategy_name=result.strategy_name,
            initial_equity=analytics.initial_equity,
            ending_equity=analytics.ending_equity,
            total_return=analytics.total_return,
            realized_pnl=analytics.realized_pnl,
            unrealized_pnl=analytics.unrealized_pnl,
            total_pnl=analytics.total_pnl,
            closed_trade_count=analytics.closed_trade_count,
            winner_count=analytics.winner_count,
            loser_count=analytics.loser_count,
            breakeven_count=analytics.breakeven_count,
            win_rate=analytics.win_rate,
            average_trade_return=analytics.average_trade_return,
            median_trade_return=analytics.median_trade_return,
            best_trade_return=analytics.best_trade_return,
            worst_trade_return=analytics.worst_trade_return,
            peak_equity=analytics.peak_equity,
            maximum_drawdown=analytics.maximum_drawdown,
            max_drawdown_peak_date=analytics.max_drawdown_peak_date,
            max_drawdown_trough_date=analytics.max_drawdown_trough_date,
            exposed_bar_count=analytics.exposed_bar_count,
            total_bar_count=analytics.total_bar_count,
            exposure=analytics.exposure,
            drawdown_series=[DrawdownPointSchema.from_domain(p) for p in analytics.drawdown_series],
        )
