from __future__ import annotations

from typing import Optional

from pydantic import BaseModel

from app.instruments.models import Instrument


class InstrumentSchema(BaseModel):
    symbol: str
    exchange: str
    name: str
    provider_symbol: str
    instrument_type: str
    status: str
    isin: Optional[str] = None
    series: Optional[str] = None

    @classmethod
    def from_domain(cls, instrument: Instrument) -> "InstrumentSchema":
        return cls(
            symbol=instrument.symbol,
            exchange=instrument.exchange.value,
            name=instrument.name,
            provider_symbol=instrument.provider_symbol,
            instrument_type=instrument.instrument_type.value,
            status=instrument.status.value,
            isin=instrument.isin,
            series=instrument.series,
        )


class InstrumentSearchResponse(BaseModel):
    results: list[InstrumentSchema]
