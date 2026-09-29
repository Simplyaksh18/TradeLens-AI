from datetime import date, timedelta

import pytest
from fastapi.testclient import TestClient

from app.api.dependencies import get_instrument_master, get_market_data_service
from app.core.exceptions import InstrumentNotFoundError
from app.instruments.models import Exchange, Instrument, InstrumentStatus, InstrumentType
from app.main import app
from app.market_data.models import OHLCVBar, OHLCVSeries

RELIANCE = Instrument(
    symbol="RELIANCE",
    exchange=Exchange.NSE,
    name="Reliance Industries Limited",
    provider_symbol="RELIANCE.NS",
    instrument_type=InstrumentType.EQUITY,
    status=InstrumentStatus.ACTIVE,
    isin="INE002A01018",
    series="EQ",
)

INFY = Instrument(
    symbol="INFY",
    exchange=Exchange.NSE,
    name="Infosys Limited",
    provider_symbol="INFY.NS",
    instrument_type=InstrumentType.EQUITY,
    status=InstrumentStatus.ACTIVE,
)


class FakeInstrumentMaster:
    """Deterministic in-memory stand-in for InstrumentMaster. No filesystem, no network."""

    def __init__(self, instruments=(RELIANCE, INFY)):
        self._by_symbol = {i.symbol: i for i in instruments}

    def resolve(self, symbol: str) -> Instrument:
        instrument = self._by_symbol.get(symbol.strip().upper())
        if instrument is None:
            raise InstrumentNotFoundError(symbol)
        return instrument

    def search(self, query: str, limit: int = 20):
        needle = query.strip().upper()
        matches = [i for i in self._by_symbol.values() if needle in i.symbol or needle in i.name.upper()]
        return matches[:limit]


def make_market_series(n=90, symbol="RELIANCE.NS", interval="1d", start=date(2024, 1, 1)):
    """Reused pattern (also used in Phase 1C/1D tests): warm-up, then a
    trend + reversal that naturally produces INSUFFICIENT_DATA, BUY, and
    NO_SIGNAL across the series."""
    bars = []
    close = 100.0
    for i in range(n):
        if i < 50:
            close += 0.01
        elif i < 65:
            close += 3.0
        else:
            close -= 3.0
        d = start + timedelta(days=i)
        bars.append(
            OHLCVBar(date=d, open=close - 1, high=close + 2, low=close - 2, close=close,
                     adj_close=close, volume=1000 + i)
        )
    return OHLCVSeries(provider_symbol=symbol, interval=interval, bars=tuple(bars))


class FakeMarketDataService:
    """Deterministic stand-in for MarketDataService. Returns a fixed
    (or exception-raising) result and counts calls, without touching any
    provider, cache, or the network."""

    def __init__(self, series: OHLCVSeries = None, raise_exc: Exception = None):
        self._series = series if series is not None else make_market_series()
        self._raise_exc = raise_exc
        self.calls = []

    def get_history(self, symbol, interval, start_date, end_date, today=None):
        self.calls.append((symbol, interval, start_date, end_date))
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._series.sliced(start_date, end_date)


@pytest.fixture
def fake_instrument_master():
    return FakeInstrumentMaster()


@pytest.fixture
def fake_market_data_service():
    return FakeMarketDataService()


@pytest.fixture
def client(fake_instrument_master, fake_market_data_service):
    app.dependency_overrides[get_instrument_master] = lambda: fake_instrument_master
    app.dependency_overrides[get_market_data_service] = lambda: fake_market_data_service
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()
