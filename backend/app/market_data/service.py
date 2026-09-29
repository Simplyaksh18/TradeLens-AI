"""Orchestrates instrument resolution, cache lookups, and provider calls.

Consumer -> MarketDataService -> cache -> (on miss) MarketDataProvider

This is the only layer that talks to both the instrument master and a
market-data provider — neither of those packages depends on the other.
"""

from __future__ import annotations

from datetime import date as Date
from typing import Optional

from app.core.exceptions import EmptyProviderResponseError, NoDataForPeriodError
from app.instruments.master import InstrumentMaster
from app.market_data.cache import HistoricalDataCache, compute_missing_ranges
from app.market_data.models import OHLCVSeries
from app.market_data.provider_base import MarketDataProvider


class MarketDataService:
    def __init__(
        self,
        provider: MarketDataProvider,
        cache: HistoricalDataCache,
        instrument_master: InstrumentMaster,
        provider_name: str = "yfinance",
    ):
        self._provider = provider
        self._cache = cache
        self._instrument_master = instrument_master
        self._provider_name = provider_name

    def get_history(
        self,
        symbol: str,
        interval: str,
        start_date: Date,
        end_date: Date,
        today: Optional[Date] = None,
    ) -> OHLCVSeries:
        """Return normalized OHLCV history for `symbol` covering [start_date, end_date].

        Raises:
            InstrumentNotFoundError: `symbol` is not in the local instrument master.
            NoDataForPeriodError: the instrument is valid but the provider had
                no bars for a range that needed fetching.
            RateLimitedError, ProviderUnavailableError,
            MalformedProviderResponseError, UnclassifiedProviderError:
                propagated from the provider layer, unchanged.
        """
        instrument = self._instrument_master.resolve(symbol)
        resolved_today = today or Date.today()

        cached_meta = self._cache.load_meta(
            self._provider_name, instrument.provider_symbol, interval
        )
        missing_ranges = compute_missing_ranges(start_date, end_date, cached_meta, resolved_today)

        for range_start, range_end in missing_ranges:
            try:
                fetched = self._provider.get_history(
                    instrument.provider_symbol, interval, range_start, range_end
                )
            except EmptyProviderResponseError as exc:
                # The instrument master already confirmed this symbol is a
                # real NSE equity, so an empty provider response here means
                # "no data for this period", not "unknown symbol".
                raise NoDataForPeriodError(
                    instrument.provider_symbol, range_start, range_end
                ) from exc

            self._cache.merge_and_write(
                self._provider_name,
                instrument.provider_symbol,
                interval,
                fetched,
                range_start,
                range_end,
                resolved_today,
            )

        return self._cache.read_range(
            self._provider_name, instrument.provider_symbol, interval, start_date, end_date
        )
