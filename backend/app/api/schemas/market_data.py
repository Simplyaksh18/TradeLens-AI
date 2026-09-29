from __future__ import annotations

from datetime import date as Date
from typing import Optional

from pydantic import BaseModel

from app.market_data.models import OHLCVBar, OHLCVSeries


class OHLCVBarSchema(BaseModel):
    date: Date
    open: float
    high: float
    low: float
    close: float
    adj_close: Optional[float]
    volume: int

    @classmethod
    def from_domain(cls, bar: OHLCVBar) -> "OHLCVBarSchema":
        return cls(
            date=bar.date, open=bar.open, high=bar.high, low=bar.low,
            close=bar.close, adj_close=bar.adj_close, volume=bar.volume,
        )


class MarketDataResponse(BaseModel):
    provider_symbol: str
    interval: str
    bars: list[OHLCVBarSchema]

    @classmethod
    def from_domain(cls, series: OHLCVSeries) -> "MarketDataResponse":
        return cls(
            provider_symbol=series.provider_symbol,
            interval=series.interval,
            bars=[OHLCVBarSchema.from_domain(b) for b in series.bars],
        )
