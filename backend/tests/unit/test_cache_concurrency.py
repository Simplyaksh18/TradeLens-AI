"""Concurrency test for HistoricalDataCache (Phase 1E section 15).

HistoricalDataCache holds no in-memory state; every operation reads/writes
the filesystem directly (see its module docstring). The real risk under
concurrent FastAPI requests is a reader observing a torn/partially-written
file, or two writers corrupting each other's output, when two requests race
for the same (provider, symbol, interval) key. This test simulates that
race with a slow FAKE provider (no network) and asserts: no exception, no
corrupted file, and identical results across all concurrent callers.

Duplicate provider calls on a simultaneous cache miss are still possible
(and asserted as acceptable, not corrupting) — see cache.py's docstring for
why no per-key lock was added for that specific inefficiency.
"""

import threading
import time
from datetime import date

from app.instruments.models import Exchange, Instrument, InstrumentStatus, InstrumentType
from app.market_data.cache import HistoricalDataCache
from app.market_data.models import OHLCVBar, OHLCVSeries
from app.market_data.provider_base import MarketDataProvider
from app.market_data.service import MarketDataService


class _SlowFakeProvider(MarketDataProvider):
    """Deterministic, offline provider with an artificial delay to widen the
    race window between concurrent get_history calls."""

    def __init__(self, series: OHLCVSeries):
        self._series = series
        self._lock = threading.Lock()
        self.call_count = 0

    def get_history(self, provider_symbol, interval, start_date, end_date):
        with self._lock:
            self.call_count += 1
        time.sleep(0.01)
        return self._series.sliced(start_date, end_date)


class _FakeInstrumentMaster:
    def resolve(self, symbol):
        return Instrument(
            symbol=symbol, exchange=Exchange.NSE, name="Test Co",
            provider_symbol=f"{symbol}.NS", instrument_type=InstrumentType.EQUITY,
            status=InstrumentStatus.ACTIVE,
        )


def _fixed_series():
    bars = tuple(
        OHLCVBar(date=date(2024, 1, i), open=1.0, high=2.0, low=0.5, close=1.5, adj_close=1.5, volume=100)
        for i in range(1, 11)
    )
    return OHLCVSeries(provider_symbol="RELIANCE.NS", interval="1d", bars=bars)


def test_concurrent_identical_requests_do_not_corrupt_cache(tmp_path):
    cache = HistoricalDataCache(tmp_path)
    provider = _SlowFakeProvider(_fixed_series())
    service = MarketDataService(provider, cache, _FakeInstrumentMaster())

    results = []
    errors = []
    lock = threading.Lock()

    def worker():
        try:
            result = service.get_history("RELIANCE", "1d", date(2024, 1, 1), date(2024, 1, 10))
            with lock:
                results.append(result)
        except Exception as exc:  # noqa: BLE001 - we want to see ANY failure
            with lock:
                errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"concurrent requests raised: {errors}"
    assert len(results) == 8
    assert all(r.bars == results[0].bars for r in results)

    # The cache file itself must still be readable and consistent afterward
    # (proves no torn/corrupted Parquet file from racing writers).
    final = cache.read_range("yfinance", "RELIANCE.NS", "1d", date(2024, 1, 1), date(2024, 1, 10))
    assert final.bars == results[0].bars
