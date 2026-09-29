"""Provider-independent interface for historical market-data retrieval.

Only the single method TradeLens currently needs. Do not add speculative
methods (quotes, fundamentals, options, etc.) until a real consumer needs them.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import date as Date

from app.market_data.models import OHLCVSeries


class MarketDataProvider(ABC):
    """Abstract source of normalized historical OHLCV data.

    Implementations must raise only the domain exceptions defined in
    `app.core.exceptions` — no provider-specific exception type (e.g. from
    yfinance) may cross this boundary.
    """

    @abstractmethod
    def get_history(
        self,
        provider_symbol: str,
        interval: str,
        start_date: Date,
        end_date: Date,
    ) -> OHLCVSeries:
        """Fetch normalized historical bars for one instrument.

        Args:
            provider_symbol: the provider-specific ticker (e.g. "RELIANCE.NS").
            interval: bar interval, e.g. "1d". Phase 1 only exercises "1d".
            start_date: inclusive start of the requested range.
            end_date: inclusive end of the requested range.

        Returns:
            OHLCVSeries with bars sorted ascending, deduplicated by date,
            containing only bars within [start_date, end_date] that the
            provider actually returned (no forward-fill/interpolation).

        Raises:
            EmptyProviderResponseError, RateLimitedError,
            ProviderUnavailableError, MalformedProviderResponseError,
            UnclassifiedProviderError.
        """
        raise NotImplementedError
