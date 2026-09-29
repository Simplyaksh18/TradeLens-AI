from __future__ import annotations

from datetime import date as Date
from typing import Optional

from pydantic import BaseModel

from app.outcomes.models import SignalOutcome, SignalOutcomeSeries


class SignalOutcomeSchema(BaseModel):
    date: Date
    decision: str
    reference_close: float
    forward_close_5d: Optional[float]
    forward_return_5d: Optional[float]
    forward_close_10d: Optional[float]
    forward_return_10d: Optional[float]
    mae_10d: Optional[float]
    mfe_10d: Optional[float]
    available_forward_bars: int

    @classmethod
    def from_domain(cls, outcome: SignalOutcome) -> "SignalOutcomeSchema":
        return cls(
            date=outcome.date,
            decision=outcome.decision.value,
            reference_close=outcome.reference_close,
            forward_close_5d=outcome.forward_close_5d,
            forward_return_5d=outcome.forward_return_5d,
            forward_close_10d=outcome.forward_close_10d,
            forward_return_10d=outcome.forward_return_10d,
            mae_10d=outcome.mae_10d,
            mfe_10d=outcome.mfe_10d,
            available_forward_bars=outcome.available_forward_bars,
        )


class SignalOutcomeSeriesResponse(BaseModel):
    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str
    outcomes: list[SignalOutcomeSchema]

    @classmethod
    def from_domain(cls, series: SignalOutcomeSeries) -> "SignalOutcomeSeriesResponse":
        return cls(
            provider_symbol=series.provider_symbol,
            interval=series.interval,
            strategy_id=series.strategy_id,
            strategy_name=series.strategy_name,
            outcomes=[SignalOutcomeSchema.from_domain(o) for o in series.outcomes],
        )
