"""Phase 2B domain model: deterministic single-position backtesting.

Phase 2A asked "what happened after every historical BUY observation?"
(each BUY stays an independent research observation). Phase 2B asks a
different question: "what would have happened if an executable trading
system acted on these strategy decisions?" — so here, consecutive BUY
evaluations while already LONG must NOT create repeated entries. These are
deliberately different models; Phase 2A's semantics are frozen/ACCEPTED and
are not touched by this package.

Execution timing (frozen V1, see CLAUDE.md Phase 2B): a strategy evaluation
on bar T reflects information through T's Close and can only affect
execution starting at bar T+1's OPEN — never T's own OPEN. Entry/exit
"signal" dates (when the decision was observed) and "execution" dates
(when the fill actually happened) are always distinct fields, never
conflated.

Price policy: `entry_price`/`exit_price` are always raw OPEN; equity
mark-to-market uses raw CLOSE. Never adjusted OHLC, never Phase 2A's
`reference_close`.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date


@dataclass(frozen=True)
class BacktestConfig:
    """V1 baseline is zero-cost/zero-slippage, kept as explicit fields (not
    a silent hardcoded assumption) so a later phase can introduce a real
    cost model without changing this shape. Phase 2B does not itself define
    what a nonzero cost/slippage would mean, so nonzero values are rejected
    explicitly (see engine._validate_config) rather than silently ignored.
    """

    initial_capital: float = 100_000.0
    transaction_cost: float = 0.0
    slippage: float = 0.0


@dataclass(frozen=True)
class ExecutedTrade:
    entry_signal_date: Date
    entry_date: Date
    entry_price: float
    exit_signal_date: Date
    exit_date: Date
    exit_price: float
    quantity: int
    gross_pnl: float
    gross_return: float
    # net_pnl == gross_pnl under the V1 zero-cost baseline; kept as its own
    # field so a future cost model changes only its computation, not callers.
    net_pnl: float


@dataclass(frozen=True)
class OpenPosition:
    """A LONG position still open at the end of the requested series.

    `pending_exit_signal_date` is set when a NO_SIGNAL evaluation scheduled
    an exit but no further trading bar existed to execute it at (end-of-data
    Case 3) — the position is explicitly still open, never fabricated as
    closed.
    """

    entry_signal_date: Date
    entry_date: Date
    entry_price: float
    quantity: int
    pending_exit_signal_date: Date | None


@dataclass(frozen=True)
class EquityPoint:
    date: Date
    cash: float
    position_quantity: int
    position_market_value: float
    equity: float


@dataclass(frozen=True)
class BacktestResult:
    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str
    config: BacktestConfig
    trades: tuple[ExecutedTrade, ...]
    open_position: OpenPosition | None
    # End-of-data Case 1: a final-bar BUY while FLAT had no T+1 OPEN to
    # execute at. The signal is preserved here explicitly; no trade is
    # fabricated.
    pending_entry_signal_date: Date | None
    equity_curve: tuple[EquityPoint, ...]
