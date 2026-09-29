"""Provider-independent instrument model.

Deliberately provider-independent except for the single `provider_symbol`
field, which is the resolved ticker for TradeLens's *current* active
provider (yfinance in Phase 1). If TradeLens gains a second provider later,
this field's meaning ("the symbol to hand the active provider") stays valid;
only the resolution logic that populates it changes.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


class Exchange(str, Enum):
    NSE = "NSE"


class InstrumentType(str, Enum):
    EQUITY = "EQUITY"


class InstrumentStatus(str, Enum):
    ACTIVE = "ACTIVE"


@dataclass(frozen=True)
class Instrument:
    symbol: str
    exchange: Exchange
    name: str
    provider_symbol: str
    instrument_type: InstrumentType
    status: InstrumentStatus
    isin: Optional[str] = None
    series: Optional[str] = None
