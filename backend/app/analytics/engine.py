"""Phase 2C: deterministic performance & risk analytics engine.

Consumes an already-computed Phase 2B `BacktestResult` unchanged -- never
reruns strategy rules, generates signals, executes trades, or alters
trades/equity. Analytics may look at the complete historical result (it
measures completed history) but strictly one-way: nothing computed here
ever feeds back into strategy generation, Phase 2A outcomes, or Phase 2B
execution.

Source of truth (see CLAUDE.md Phase 2C): the Phase 2B equity curve is
authoritative for portfolio/equity metrics (ending equity, drawdown,
exposure); CLOSED trades are authoritative for trade statistics. Portfolio
state is never reconstructed by re-deriving it from trades -- that would
duplicate the backtesting state machine.

Frozen V1 scope note: annualized volatility (and CAGR/Sharpe/Sortino/
Calmar/alpha/beta/benchmark comparison/VaR/CVaR/recovery duration/rolling
analytics) is explicitly DEFERRED, not implemented here -- see CLAUDE.md
Phase 2C.
"""

from __future__ import annotations

import statistics
from datetime import date as Date
from math import isfinite

from app.analytics.models import DrawdownPoint, PerformanceAnalytics
from app.backtesting.models import BacktestResult, EquityPoint
from app.core.exceptions import AnalyticsInputInvalidError


def compute_performance_analytics(result: BacktestResult) -> PerformanceAnalytics:
    """Compute Phase 2C V1 metrics for a completed backtest.

    Raises AnalyticsInputInvalidError if `result` cannot support
    well-defined analytics (see the exception's docstring). Never mutates
    `result`.
    """
    _validate(result)

    equity_curve = result.equity_curve
    initial_equity = equity_curve[0].equity
    ending_equity = equity_curve[-1].equity
    total_return = ending_equity / initial_equity - 1
    total_pnl = ending_equity - initial_equity

    closed_trades = result.trades
    closed_trade_count = len(closed_trades)
    # No epsilon: exact comparison against zero, consistent with the
    # strict-inequality convention already used by Phase 1D's strategy
    # rule (see CLAUDE.md) -- no accepted numeric-tolerance policy exists
    # to justify inventing one here.
    winner_count = sum(1 for t in closed_trades if t.net_pnl > 0)
    loser_count = sum(1 for t in closed_trades if t.net_pnl < 0)
    breakeven_count = sum(1 for t in closed_trades if t.net_pnl == 0)

    win_rate = (winner_count / closed_trade_count) if closed_trade_count > 0 else None

    trade_returns = [t.gross_return for t in closed_trades]  # V1: gross == net (zero-cost baseline).
    if trade_returns:
        average_trade_return = statistics.mean(trade_returns)
        median_trade_return = statistics.median(trade_returns)
        best_trade_return = max(trade_returns)
        worst_trade_return = min(trade_returns)
    else:
        average_trade_return = median_trade_return = best_trade_return = worst_trade_return = None

    realized_pnl = sum((t.net_pnl for t in closed_trades), 0.0)
    if result.open_position is not None:
        final_point = equity_curve[-1]
        unrealized_pnl = final_point.position_market_value - (
            result.open_position.entry_price * result.open_position.quantity
        )
    else:
        unrealized_pnl = 0.0

    drawdown_series, max_drawdown, max_dd_peak_date, max_dd_trough_date = _compute_drawdown(equity_curve)
    peak_equity = max(p.equity for p in equity_curve)

    total_bar_count = len(equity_curve)
    exposed_bar_count = sum(1 for p in equity_curve if p.position_market_value > 0)
    exposure = exposed_bar_count / total_bar_count

    return PerformanceAnalytics(
        initial_equity=initial_equity,
        ending_equity=ending_equity,
        total_return=total_return,
        realized_pnl=realized_pnl,
        unrealized_pnl=unrealized_pnl,
        total_pnl=total_pnl,
        closed_trade_count=closed_trade_count,
        winner_count=winner_count,
        loser_count=loser_count,
        breakeven_count=breakeven_count,
        win_rate=win_rate,
        average_trade_return=average_trade_return,
        median_trade_return=median_trade_return,
        best_trade_return=best_trade_return,
        worst_trade_return=worst_trade_return,
        peak_equity=peak_equity,
        maximum_drawdown=max_drawdown,
        max_drawdown_peak_date=max_dd_peak_date,
        max_drawdown_trough_date=max_dd_trough_date,
        exposed_bar_count=exposed_bar_count,
        total_bar_count=total_bar_count,
        exposure=exposure,
        drawdown_series=drawdown_series,
    )


def _compute_drawdown(equity_curve: tuple[EquityPoint, ...]) -> tuple[tuple[DrawdownPoint, ...], float, Date, Date]:
    """Running-peak drawdown series plus the maximum-drawdown peak/trough.

    Tie policy (frozen V1, see CLAUDE.md): the running peak's date updates
    ONLY when equity is strictly greater than the previous running peak
    (equal equity never replaces the existing peak date). When the minimum
    drawdown value repeats, the FIRST occurrence is kept.
    """
    points: list[DrawdownPoint] = []
    peak_dates: list[Date] = []
    running_peak = equity_curve[0].equity
    running_peak_date = equity_curve[0].date

    for p in equity_curve:
        if p.equity > running_peak:
            running_peak = p.equity
            running_peak_date = p.date
        drawdown = p.equity / running_peak - 1
        points.append(DrawdownPoint(date=p.date, equity=p.equity, running_peak=running_peak, drawdown=drawdown))
        peak_dates.append(running_peak_date)

    min_index = 0
    for i in range(1, len(points)):
        if points[i].drawdown < points[min_index].drawdown:  # strict: first occurrence wins on ties.
            min_index = i

    return tuple(points), points[min_index].drawdown, peak_dates[min_index], points[min_index].date


def _validate(result: BacktestResult) -> None:
    if len(result.equity_curve) == 0:
        raise AnalyticsInputInvalidError(
            "Cannot compute analytics for an empty equity curve -- initial/ending equity are undefined."
        )
    if not isfinite(result.config.initial_capital) or result.config.initial_capital <= 0:
        raise AnalyticsInputInvalidError(f"initial_capital must be finite and > 0, got {result.config.initial_capital!r}")

    previous_date: Date | None = None
    for p in result.equity_curve:
        if previous_date is not None and p.date <= previous_date:
            raise AnalyticsInputInvalidError(f"Equity curve dates are not strictly chronological at {p.date}")
        previous_date = p.date
        if not isfinite(p.cash):
            raise AnalyticsInputInvalidError(f"Non-finite cash at {p.date}")
        if not isfinite(p.position_market_value) or p.position_market_value < 0:
            raise AnalyticsInputInvalidError(f"Non-finite or negative position_market_value at {p.date}")
        if not isfinite(p.equity):
            raise AnalyticsInputInvalidError(f"Non-finite equity at {p.date}")

    for t in result.trades:
        if not isfinite(t.net_pnl):
            raise AnalyticsInputInvalidError(f"Non-finite net_pnl for trade exiting {t.exit_date}")
        if not isfinite(t.gross_return):
            raise AnalyticsInputInvalidError(f"Non-finite gross_return for trade exiting {t.exit_date}")
        if t.quantity <= 0:
            raise AnalyticsInputInvalidError(f"Non-positive trade quantity for trade exiting {t.exit_date}")

    if result.open_position is not None:
        op = result.open_position
        if not isfinite(op.entry_price) or op.entry_price <= 0:
            raise AnalyticsInputInvalidError("Open position entry_price must be finite and > 0")
        if op.quantity <= 0:
            raise AnalyticsInputInvalidError("Open position quantity must be > 0")
