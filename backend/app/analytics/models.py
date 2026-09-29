"""Phase 2C domain model: performance & risk analytics over a completed
Phase 2B `BacktestResult`.

Two deliberately distinct populations (see CLAUDE.md Phase 2C):
  - TRADE statistics (`closed_trade_count`, `win_rate`, the return
    distribution, `realized_pnl`) use CLOSED trades only. An open position
    is never counted as a winner/loser/breakeven/closed trade.
  - PORTFOLIO/equity statistics (`total_return`, `drawdown_series`,
    `exposure`) use the complete Phase 2B equity
    curve, so an open position's final mark-to-market value IS reflected
    there via `unrealized_pnl`/`ending_equity`.

All returns are decimal fractions (0.18 means +18%), never percentages.
`maximum_drawdown` and every `drawdown_series` value are <= 0.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date


@dataclass(frozen=True)
class DrawdownPoint:
    date: Date
    equity: float
    running_peak: float
    drawdown: float


@dataclass(frozen=True)
class PerformanceAnalytics:
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
    win_rate: float | None

    average_trade_return: float | None
    median_trade_return: float | None
    best_trade_return: float | None
    worst_trade_return: float | None

    peak_equity: float

    maximum_drawdown: float
    max_drawdown_peak_date: Date
    max_drawdown_trough_date: Date

    exposed_bar_count: int
    total_bar_count: int
    exposure: float | None

    drawdown_series: tuple[DrawdownPoint, ...]
