"""Phase 2B: deterministic single-position backtesting engine.

Consumes an already-computed Phase 1D `StrategyEvaluationSeries` and its
structurally aligned `OHLCVSeries` unchanged — never recalculates a
decision, only executes the FROZEN V1 interpretation documented below and
in CLAUDE.md Phase 2B.

Execution model (frozen V1):
  - Long only, at most one open position, no pyramiding/averaging, no
    shorting, no leverage, no fractional shares.
  - A BUY evaluation on bar T reflects information through T's Close and
    can only affect execution starting at bar T+1's OPEN. FLAT+BUY
    schedules an entry for the next bar; LONG+BUY is a no-op (stay long).
  - The first NO_SIGNAL observed while LONG schedules an exit for the next
    bar's OPEN. FLAT+NO_SIGNAL is a no-op.
  - INSUFFICIENT_DATA never triggers any action, regardless of position
    state.
  - End-of-data: a scheduled entry/exit that never reaches a bar to execute
    at is preserved explicitly (`pending_entry_signal_date` /
    `OpenPosition.pending_exit_signal_date`) — never fabricated, never
    force-closed at a bar's own Close.

Deterministic per-bar event order (must not be reordered — see CLAUDE.md):
  1. Execute any action scheduled by the PRIOR bar's evaluation, at the
     CURRENT bar's OPEN.
  2. Update position/cash state from that fill.
  3. Process the CURRENT bar's strategy evaluation.
  4. Schedule any resulting action for the NEXT bar.
  5. Compute end-of-bar equity from the CURRENT bar's raw Close.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from math import floor, isfinite

from app.backtesting.models import BacktestConfig, BacktestResult, EquityPoint, ExecutedTrade, OpenPosition
from app.core.exceptions import BacktestInputInvalidError
from app.market_data.models import OHLCVSeries
from app.strategies.models import StrategyDecision, StrategyEvaluationSeries


@dataclass
class _ActivePosition:
    entry_signal_date: Date
    entry_date: Date
    entry_price: float
    quantity: int


def run_backtest(
    market_series: OHLCVSeries,
    evaluation_series: StrategyEvaluationSeries,
    config: BacktestConfig = BacktestConfig(),
) -> BacktestResult:
    """Run the frozen V1 deterministic backtest.

    Raises BacktestInputInvalidError for structural misalignment, invalid
    prices, or an invalid config. Never mutates its inputs.
    """
    _validate_alignment(market_series, evaluation_series)
    _validate_config(config)

    bars = market_series.bars
    evaluations = evaluation_series.evaluations

    cash = config.initial_capital
    position: _ActivePosition | None = None
    pending_action: tuple[str, Date] | None = None  # ("ENTER" | "EXIT", signal_date)
    trades: list[ExecutedTrade] = []
    equity_curve: list[EquityPoint] = []

    for bar, evaluation in zip(bars, evaluations):
        # Steps 1-2: execute a fill scheduled by the PRIOR bar, at this
        # bar's OPEN. Never today's decision executed at today's OPEN.
        if pending_action is not None:
            action, signal_date = pending_action
            pending_action = None
            if action == "ENTER" and position is None:
                entry_price = bar.open
                quantity = floor(cash / entry_price)
                if quantity > 0:
                    cash -= quantity * entry_price
                    position = _ActivePosition(
                        entry_signal_date=signal_date, entry_date=bar.date, entry_price=entry_price, quantity=quantity
                    )
                # quantity <= 0: no executable position (insufficient
                # capital for even one share) -- stay FLAT, no trade.
            elif action == "EXIT" and position is not None:
                exit_price = bar.open
                gross_pnl = (exit_price - position.entry_price) * position.quantity
                gross_return = exit_price / position.entry_price - 1
                trades.append(
                    ExecutedTrade(
                        entry_signal_date=position.entry_signal_date,
                        entry_date=position.entry_date,
                        entry_price=position.entry_price,
                        exit_signal_date=signal_date,
                        exit_date=bar.date,
                        exit_price=exit_price,
                        quantity=position.quantity,
                        gross_pnl=gross_pnl,
                        gross_return=gross_return,
                        net_pnl=gross_pnl,  # V1 zero-cost baseline: net == gross.
                    )
                )
                cash += position.quantity * exit_price
                position = None

        # Steps 3-4: process the CURRENT bar's evaluation, schedule the
        # NEXT bar's action (if any).
        decision = evaluation.decision
        if decision == StrategyDecision.BUY and position is None:
            pending_action = ("ENTER", evaluation.date)
        elif decision == StrategyDecision.NO_SIGNAL and position is not None:
            pending_action = ("EXIT", evaluation.date)
        # StrategyDecision.INSUFFICIENT_DATA, LONG+BUY, and FLAT+NO_SIGNAL
        # all fall through with no scheduled action.

        # Step 5: end-of-bar equity from this bar's raw Close.
        market_value = position.quantity * bar.close if position is not None else 0.0
        equity_curve.append(
            EquityPoint(
                date=bar.date,
                cash=cash,
                position_quantity=position.quantity if position is not None else 0,
                position_market_value=market_value,
                equity=cash + market_value,
            )
        )

    open_position: OpenPosition | None = None
    pending_entry_signal_date: Date | None = None

    if pending_action is not None:
        action, signal_date = pending_action
        if action == "ENTER":
            # Case 1: final-bar BUY while FLAT, no T+1 OPEN to fill at.
            pending_entry_signal_date = signal_date
        elif action == "EXIT" and position is not None:
            # Case 3: final-bar NO_SIGNAL while LONG, no T+1 OPEN to exit at.
            open_position = OpenPosition(
                entry_signal_date=position.entry_signal_date,
                entry_date=position.entry_date,
                entry_price=position.entry_price,
                quantity=position.quantity,
                pending_exit_signal_date=signal_date,
            )
    elif position is not None:
        # Case 2: still LONG at the final bar, no exit ever scheduled.
        open_position = OpenPosition(
            entry_signal_date=position.entry_signal_date,
            entry_date=position.entry_date,
            entry_price=position.entry_price,
            quantity=position.quantity,
            pending_exit_signal_date=None,
        )

    return BacktestResult(
        provider_symbol=market_series.provider_symbol,
        interval=market_series.interval,
        strategy_id=evaluation_series.strategy_id,
        strategy_name=evaluation_series.strategy_name,
        config=config,
        trades=tuple(trades),
        open_position=open_position,
        pending_entry_signal_date=pending_entry_signal_date,
        equity_curve=tuple(equity_curve),
    )


def _validate_alignment(market_series: OHLCVSeries, evaluation_series: StrategyEvaluationSeries) -> None:
    if market_series.provider_symbol != evaluation_series.provider_symbol:
        raise BacktestInputInvalidError(
            f"Symbol mismatch: market series {market_series.provider_symbol!r} vs "
            f"evaluation series {evaluation_series.provider_symbol!r}"
        )
    if market_series.interval != evaluation_series.interval:
        raise BacktestInputInvalidError(
            f"Interval mismatch: market series {market_series.interval!r} vs "
            f"evaluation series {evaluation_series.interval!r}"
        )
    if len(market_series.bars) != len(evaluation_series.evaluations):
        raise BacktestInputInvalidError(
            f"Row count mismatch: {len(market_series.bars)} market bars vs "
            f"{len(evaluation_series.evaluations)} evaluations"
        )

    previous_date: Date | None = None
    for bar, evaluation in zip(market_series.bars, evaluation_series.evaluations):
        if bar.date != evaluation.date:
            raise BacktestInputInvalidError(f"Date misalignment: market bar date {bar.date} != evaluation date {evaluation.date}")
        if previous_date is not None and bar.date <= previous_date:
            raise BacktestInputInvalidError(f"Market rows are not strictly chronological at {bar.date}")
        previous_date = bar.date
        if not isfinite(bar.open) or bar.open <= 0:
            raise BacktestInputInvalidError(f"Non-finite or non-positive open at {bar.date}")
        if not isfinite(bar.close) or bar.close <= 0:
            raise BacktestInputInvalidError(f"Non-finite or non-positive close at {bar.date}")


def _validate_config(config: BacktestConfig) -> None:
    if not isfinite(config.initial_capital) or config.initial_capital <= 0:
        raise BacktestInputInvalidError(f"initial_capital must be finite and > 0, got {config.initial_capital!r}")
    for name, value in (("transaction_cost", config.transaction_cost), ("slippage", config.slippage)):
        if not isfinite(value) or value < 0:
            raise BacktestInputInvalidError(f"{name} must be finite and >= 0, got {value!r}")
        if value != 0.0:
            raise BacktestInputInvalidError(
                f"{name} must be 0.0 in Phase 2B V1 -- no cost/slippage model is defined yet to apply a nonzero value"
            )
