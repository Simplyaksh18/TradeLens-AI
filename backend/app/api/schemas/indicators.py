from __future__ import annotations

from datetime import date as Date
from typing import Optional

from pydantic import BaseModel

from app.indicators.models import IndicatorRow, IndicatorSeries


class IndicatorRowSchema(BaseModel):
    date: Date
    sma20: Optional[float]
    sma50: Optional[float]
    rsi14: Optional[float]
    average_volume: Optional[float]
    volume_ratio: Optional[float]

    @classmethod
    def from_domain(cls, row: IndicatorRow) -> "IndicatorRowSchema":
        return cls(
            date=row.date, sma20=row.sma20, sma50=row.sma50, rsi14=row.rsi14,
            average_volume=row.average_volume, volume_ratio=row.volume_ratio,
        )


class IndicatorResponse(BaseModel):
    provider_symbol: str
    interval: str
    rows: list[IndicatorRowSchema]

    @classmethod
    def from_domain(cls, series: IndicatorSeries) -> "IndicatorResponse":
        return cls(
            provider_symbol=series.provider_symbol,
            interval=series.interval,
            rows=[IndicatorRowSchema.from_domain(r) for r in series.rows],
        )
