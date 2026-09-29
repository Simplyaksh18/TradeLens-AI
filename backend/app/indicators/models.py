"""Provider-independent indicator output contract.

Deliberately holds only calculated values keyed by trading date — no
strategy/signal fields belong here (see app.indicators, Phase 1D owns
strategy evaluation). Warm-up periods are represented as `None`, never
fabricated or backfilled.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from typing import Optional


@dataclass(frozen=True)
class IndicatorRow:
    date: Date
    sma20: Optional[float]
    sma50: Optional[float]
    rsi14: Optional[float]
    average_volume: Optional[float]
    volume_ratio: Optional[float]


@dataclass(frozen=True)
class IndicatorSeries:
    provider_symbol: str
    interval: str
    rows: tuple[IndicatorRow, ...]
