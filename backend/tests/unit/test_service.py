from datetime import date

import pytest

from app.core.exceptions import (
    EmptyProviderResponseError,
    InstrumentNotFoundError,
    NoDataForPeriodError,
)
from app.instruments.master import InstrumentMaster
from app.instruments.models import Exchange, Instrument, InstrumentStatus, InstrumentType
from app.market_data.cache import HistoricalDataCache
from app.market_data.models import OHLCVBar, OHLCVSeries
from app.market_data.provider_base import MarketDataProvider
from app.market_data.service import MarketDataService

RELIANCE = Instrument(
    symbol="RELIANCE",
    exchange=Exchange.NSE,
    name="Reliance Industries Limited",
    provider_symbol="RELIANCE.NS",
    instrument_type=InstrumentType.EQUITY,
    status=InstrumentStatus.ACTIVE,
)


class FakeInstrumentMaster:
    def resolve(self, symbol: str) -> Instrument:
        if symbol.upper() != "RELIANCE":
            raise InstrumentNotFoundError(symbol)
        return RELIANCE


class FakeProvider(MarketDataProvider):
    def __init__(self, series: OHLCVSeries | None = None, raise_empty: bool = False):
        self._series = series
        self._raise_empty = raise_empty
        self.calls: list[tuple] = []

    def get_history(self, provider_symbol, interval, start_date, end_date):
        self.calls.append((provider_symbol, interval, start_date, end_date))
        if self._raise_empty:
            raise EmptyProviderResponseError(provider_symbol, start_date, end_date)
        return self._series.sliced(start_date, end_date)


def _series(dates_closes):
    bars = tuple(
        OHLCVBar(date=d, open=c, high=c, low=c, close=c, adj_close=c, volume=100)
        for d, c in dates_closes
    )
    return OHLCVSeries(provider_symbol="RELIANCE.NS", interval="1d", bars=bars)


def test_unknown_symbol_raises_instrument_not_found(tmp_path):
    service = MarketDataService(FakeProvider(), HistoricalDataCache(tmp_path), FakeInstrumentMaster())
    with pytest.raises(InstrumentNotFoundError):
        service.get_history("NOTREAL", "1d", date(2024, 1, 1), date(2024, 1, 5))


def test_cache_miss_calls_provider_and_populates_cache(tmp_path):
    provider = FakeProvider(series=_series([(date(2024, 1, 1), 1.0), (date(2024, 1, 2), 2.0)]))
    cache = HistoricalDataCache(tmp_path)
    service = MarketDataService(provider, cache, FakeInstrumentMaster())

    result = service.get_history("RELIANCE", "1d", date(2024, 1, 1), date(2024, 1, 2), today=date(2024, 1, 3))

    assert len(provider.calls) == 1
    assert len(result.bars) == 2


def test_cache_hit_does_not_call_provider(tmp_path):
    cache = HistoricalDataCache(tmp_path)
    cache.merge_and_write(
        "yfinance", "RELIANCE.NS", "1d",
        _series([(date(2024, 1, i), float(i)) for i in range(1, 11)]),
        date(2024, 1, 1), date(2024, 1, 10), today=date(2024, 1, 11),
    )
    provider = FakeProvider()
    service = MarketDataService(provider, cache, FakeInstrumentMaster())

    result = service.get_history("RELIANCE", "1d", date(2024, 1, 3), date(2024, 1, 5), today=date(2024, 1, 11))

    assert provider.calls == []
    assert [b.date for b in result.bars] == [date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 5)]


def test_empty_provider_response_reclassified_as_no_data_for_period(tmp_path):
    provider = FakeProvider(raise_empty=True)
    service = MarketDataService(provider, HistoricalDataCache(tmp_path), FakeInstrumentMaster())

    with pytest.raises(NoDataForPeriodError):
        service.get_history("RELIANCE", "1d", date(2024, 1, 1), date(2024, 1, 5))
