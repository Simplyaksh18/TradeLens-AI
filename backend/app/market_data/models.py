"""Provider-independent market-data models.

No field here may depend on a specific provider's response shape (e.g. no
yfinance MultiIndex columns). Providers normalize into these models at the
provider boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from typing import Optional


@dataclass(frozen=True)
class OHLCVBar:
    """A single normalized daily bar.

    `close` is the raw (unadjusted) traded close, exactly as reported by the
    exchange/provider. `adj_close` is the provider's corporate-action-adjusted
    close. TradeLens deliberately keeps these distinct (see
    YFinanceProvider / ADR note in providers/yfinance_provider.py) — no
    quantitative code may treat `close` and `adj_close` as interchangeable.

    `adj_close` may be None if a provider cannot supply it.
    """

    date: Date
    open: float
    high: float
    low: float
    close: float
    adj_close: Optional[float]
    volume: int


@dataclass(frozen=True)
class OHLCVSeries:
    """An ordered, deduplicated series of daily bars for one instrument/interval.

    `provider_symbol` (not the TradeLens `symbol`) is stored here because this
    is the provider-facing representation used by the cache and provider
    layers, which are not aware of the instrument master.

    Invariants (enforced by callers that construct this, see
    providers/yfinance_normalization.py and market_data/cache.py):
      - `bars` sorted ascending by date
      - no duplicate dates
    """

    provider_symbol: str
    interval: str
    bars: tuple[OHLCVBar, ...]

    @property
    def start_date(self) -> Optional[Date]:
        return self.bars[0].date if self.bars else None

    @property
    def end_date(self) -> Optional[Date]:
        return self.bars[-1].date if self.bars else None

    def sliced(self, start_date: Date, end_date: Date) -> "OHLCVSeries":
        """Return a new series containing only bars within [start_date, end_date]."""
        filtered = tuple(b for b in self.bars if start_date <= b.date <= end_date)
        return OHLCVSeries(
            provider_symbol=self.provider_symbol,
            interval=self.interval,
            bars=filtered,
        )
