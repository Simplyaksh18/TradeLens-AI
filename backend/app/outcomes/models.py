"""Phase 2A domain model: historical BUY-signal outcome measurement.

This is a research primitive, NOT the Phase 2B portfolio backtester (see
CLAUDE.md Phase 2A). It answers "what happened to price after a historical
BUY signal", nothing about execution, position sizing, fees, or portfolio
state.

`reference_close` is deliberately named for what it is: the same raw Close
the Phase 1D strategy already evaluated at the signal date, used here only
as an observational baseline for measuring what happened afterward. It is
NOT an execution fill price (`entry_price`/`execution_price` would imply an
assumption this phase does not make — that belongs to Phase 2B).

All `+5D`/`+10D` fields are TRADING-BAR horizons (the Nth subsequent
available bar in the series), never calendar-day offsets. A `None` field
means that horizon's bar(s) do not exist in the supplied series (censored
by insufficient trailing data), never a zero/loss.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date

from app.strategies.models import StrategyDecision


@dataclass(frozen=True)
class SignalOutcome:
    date: Date
    decision: StrategyDecision
    reference_close: float
    forward_close_5d: float | None
    forward_return_5d: float | None
    forward_close_10d: float | None
    forward_return_10d: float | None
    mae_10d: float | None
    mfe_10d: float | None
    # Count of trading bars actually available after the signal date in the
    # supplied series (uncapped) — lets a caller distinguish "9 bars existed
    # but 10D still isn't computed" from "signal was on the final row".
    available_forward_bars: int


@dataclass(frozen=True)
class SignalOutcomeSeries:
    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str
    outcomes: tuple[SignalOutcome, ...]
