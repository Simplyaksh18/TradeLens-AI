from datetime import date
from pathlib import Path

from app.market_data.cache import CacheMeta, HistoricalDataCache, compute_missing_ranges
from app.market_data.models import OHLCVBar, OHLCVSeries


def _series(dates_closes: list[tuple[date, float]], provider_symbol="RELIANCE.NS") -> OHLCVSeries:
    bars = tuple(
        OHLCVBar(date=d, open=c, high=c, low=c, close=c, adj_close=c, volume=100)
        for d, c in dates_closes
    )
    return OHLCVSeries(provider_symbol=provider_symbol, interval="1d", bars=bars)


# ---- compute_missing_ranges (pure function) ----


def test_no_cache_means_entire_range_missing():
    result = compute_missing_ranges(date(2024, 1, 1), date(2024, 1, 31), None, date(2024, 2, 1))
    assert result == [(date(2024, 1, 1), date(2024, 1, 31))]


def test_fully_covered_and_fresh_range_is_not_missing():
    meta = CacheMeta(date(2020, 1, 1), date(2025, 12, 31), last_refreshed=date(2026, 1, 1))
    result = compute_missing_ranges(date(2024, 1, 1), date(2024, 12, 31), meta, today=date(2026, 1, 1))
    assert result == []


def test_range_extending_before_cache_start_is_missing():
    meta = CacheMeta(date(2024, 1, 1), date(2024, 12, 31), last_refreshed=date(2026, 1, 1))
    result = compute_missing_ranges(date(2023, 1, 1), date(2024, 6, 30), meta, today=date(2026, 1, 1))
    assert result == [(date(2023, 1, 1), date(2023, 12, 31))]


def test_range_extending_past_stale_cache_end_refetches_with_overlap():
    meta = CacheMeta(date(2024, 1, 1), date(2024, 6, 1), last_refreshed=date(2024, 6, 2))
    result = compute_missing_ranges(date(2024, 1, 1), date(2024, 6, 10), meta, today=date(2024, 6, 10))
    assert result == [(date(2024, 5, 27), date(2024, 6, 10))]  # 5-day overlap


def test_range_extending_past_cache_end_refreshed_today_has_no_overlap():
    meta = CacheMeta(date(2024, 1, 1), date(2024, 6, 1), last_refreshed=date(2024, 6, 10))
    result = compute_missing_ranges(date(2024, 1, 1), date(2024, 6, 10), meta, today=date(2024, 6, 10))
    assert result == [(date(2024, 6, 2), date(2024, 6, 10))]


# ---- HistoricalDataCache (filesystem-backed) ----


def test_write_then_read_round_trip(tmp_path):
    cache = HistoricalDataCache(tmp_path)
    series = _series([(date(2024, 1, 1), 100.0), (date(2024, 1, 2), 101.0)])

    cache.merge_and_write(
        "yfinance", "RELIANCE.NS", "1d", series,
        date(2024, 1, 1), date(2024, 1, 2), today=date(2024, 1, 3),
    )
    result = cache.read_range("yfinance", "RELIANCE.NS", "1d", date(2024, 1, 1), date(2024, 1, 2))

    assert len(result.bars) == 2
    assert result.bars[0].close == 100.0


def test_read_range_trims_to_requested_subrange(tmp_path):
    cache = HistoricalDataCache(tmp_path)
    series = _series([(date(2024, 1, i), float(i)) for i in range(1, 11)])
    cache.merge_and_write(
        "yfinance", "RELIANCE.NS", "1d", series,
        date(2024, 1, 1), date(2024, 1, 10), today=date(2024, 1, 11),
    )

    result = cache.read_range("yfinance", "RELIANCE.NS", "1d", date(2024, 1, 3), date(2024, 1, 5))

    assert [b.date for b in result.bars] == [date(2024, 1, 3), date(2024, 1, 4), date(2024, 1, 5)]


def test_merge_overwrites_overlapping_dates_with_new_data(tmp_path):
    cache = HistoricalDataCache(tmp_path)
    original = _series([(date(2024, 1, 1), 100.0), (date(2024, 1, 2), 101.0)])
    cache.merge_and_write(
        "yfinance", "RELIANCE.NS", "1d", original,
        date(2024, 1, 1), date(2024, 1, 2), today=date(2024, 1, 3),
    )

    revision = _series([(date(2024, 1, 2), 999.0), (date(2024, 1, 3), 102.0)])
    cache.merge_and_write(
        "yfinance", "RELIANCE.NS", "1d", revision,
        date(2024, 1, 2), date(2024, 1, 3), today=date(2024, 1, 4),
    )

    result = cache.read_range("yfinance", "RELIANCE.NS", "1d", date(2024, 1, 1), date(2024, 1, 3))
    by_date = {b.date: b.close for b in result.bars}
    assert by_date[date(2024, 1, 2)] == 999.0
    assert by_date[date(2024, 1, 3)] == 102.0


def test_read_range_on_missing_cache_returns_empty_series(tmp_path):
    cache = HistoricalDataCache(tmp_path)
    result = cache.read_range("yfinance", "NOPE.NS", "1d", date(2024, 1, 1), date(2024, 1, 2))
    assert result.bars == ()


def test_load_meta_reflects_merged_coverage(tmp_path):
    cache = HistoricalDataCache(tmp_path)
    cache.merge_and_write(
        "yfinance", "RELIANCE.NS", "1d",
        _series([(date(2024, 3, 1), 1.0)]),
        date(2024, 3, 1), date(2024, 3, 1), today=date(2024, 3, 2),
    )
    cache.merge_and_write(
        "yfinance", "RELIANCE.NS", "1d",
        _series([(date(2024, 1, 1), 1.0)]),
        date(2024, 1, 1), date(2024, 1, 1), today=date(2024, 3, 3),
    )

    meta = cache.load_meta("yfinance", "RELIANCE.NS", "1d")

    assert meta.start_date == date(2024, 1, 1)
    assert meta.end_date == date(2024, 3, 1)
    assert meta.last_refreshed == date(2024, 3, 3)


# ---- Regression: weekend/holiday-boundary coverage bug (Gate A discovery) ----
# A requested start date that falls on a non-trading day (e.g. a Saturday)
# means the provider's first RETURNED bar is later than the REQUESTED start.
# Coverage metadata must still reflect the requested start, not the first
# bar's date, or a repeat of the same request will wrongly think the
# leading gap was never queried and re-fetch it (which then legitimately
# returns nothing and must not be misreported as an error).


def test_coverage_uses_queried_range_not_first_returned_bar_date(tmp_path):
    cache = HistoricalDataCache(tmp_path)
    # Requested Sat Jan 6 -> Wed Jan 10, but the provider only has bars from
    # Mon Jan 8 (the first trading day in that window) onward.
    fetched = _series([(date(2024, 1, 8), 1.0), (date(2024, 1, 9), 2.0), (date(2024, 1, 10), 3.0)])

    cache.merge_and_write(
        "yfinance", "RELIANCE.NS", "1d", fetched,
        date(2024, 1, 6), date(2024, 1, 10), today=date(2024, 1, 10),
    )

    meta = cache.load_meta("yfinance", "RELIANCE.NS", "1d")
    assert meta.start_date == date(2024, 1, 6)  # the REQUESTED start, not Jan 8


def test_repeat_request_spanning_a_weekend_start_is_fully_served_from_cache():
    from app.core.exceptions import EmptyProviderResponseError, NoDataForPeriodError
    from app.instruments.master import InstrumentMaster
    from app.instruments.models import Exchange, Instrument, InstrumentStatus, InstrumentType
    from app.market_data.provider_base import MarketDataProvider
    from app.market_data.service import MarketDataService

    class FakeInstrumentMaster:
        def resolve(self, symbol):
            return Instrument(
                symbol="RELIANCE", exchange=Exchange.NSE, name="Reliance",
                provider_symbol="RELIANCE.NS", instrument_type=InstrumentType.EQUITY,
                status=InstrumentStatus.ACTIVE,
            )

    class WeekendAwareFakeProvider(MarketDataProvider):
        """Mimics a real provider: a requested range starting on a weekend
        returns bars only from the first actual trading day onward, and a
        request entirely inside the weekend returns nothing at all."""

        def __init__(self):
            self.calls = 0

        def get_history(self, provider_symbol, interval, start_date, end_date):
            self.calls += 1
            full = _series([(date(2024, 1, 8), 1.0), (date(2024, 1, 9), 2.0), (date(2024, 1, 10), 3.0)])
            sliced = full.sliced(start_date, end_date)
            if not sliced.bars:
                raise EmptyProviderResponseError(provider_symbol, start_date, end_date)
            return sliced

    import tempfile
    with tempfile.TemporaryDirectory() as tmp:
        cache = HistoricalDataCache(Path(tmp))
        provider = WeekendAwareFakeProvider()
        service = MarketDataService(provider, cache, FakeInstrumentMaster())

        result1 = service.get_history(
            "RELIANCE", "1d", date(2024, 1, 6), date(2024, 1, 10), today=date(2024, 1, 10)
        )
        assert provider.calls == 1
        assert len(result1.bars) == 3

        # Identical repeat request must be served entirely from cache.
        result2 = service.get_history(
            "RELIANCE", "1d", date(2024, 1, 6), date(2024, 1, 10), today=date(2024, 1, 10)
        )
        assert provider.calls == 1  # no additional provider call
        assert result2.bars == result1.bars
