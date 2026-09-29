from datetime import date

import pandas as pd
import pytest

from app.core.exceptions import MalformedProviderResponseError
from app.market_data.providers.yfinance_normalization import normalize_yfinance_history


def _make_multiindex_df(rows: list[dict], symbol: str = "RELIANCE.NS") -> pd.DataFrame:
    """Build a DataFrame matching yfinance's real download() shape for one
    ticker with auto_adjust=False, as observed in the Phase 1.0 POC:
    MultiIndex columns (field, ticker), DatetimeIndex named 'Date'.
    """
    dates = pd.to_datetime([r["date"] for r in rows])
    fields = ["Adj Close", "Close", "High", "Low", "Open", "Volume"]
    columns = pd.MultiIndex.from_product([fields, [symbol]], names=["Price", "Ticker"])
    data = {
        (field, symbol): [r[field.lower().replace(" ", "_")] for r in rows] for field in fields
    }
    df = pd.DataFrame(data, index=dates, columns=columns)
    df.index.name = "Date"
    return df


SAMPLE_ROWS = [
    {"date": "2026-01-02", "open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0, "adj_close": 104.0, "volume": 1000},
    {"date": "2026-01-03", "open": 104.0, "high": 108.0, "low": 103.0, "close": 107.0, "adj_close": 106.5, "volume": 1500},
]


def test_normalizes_multiindex_dataframe_into_ohlcv_series():
    df = _make_multiindex_df(SAMPLE_ROWS)

    series = normalize_yfinance_history(df, "RELIANCE.NS", "1d")

    assert series.provider_symbol == "RELIANCE.NS"
    assert series.interval == "1d"
    assert len(series.bars) == 2
    assert series.start_date == date(2026, 1, 2)
    assert series.end_date == date(2026, 1, 3)


def test_preserves_raw_close_distinct_from_adj_close():
    df = _make_multiindex_df(SAMPLE_ROWS)
    series = normalize_yfinance_history(df, "RELIANCE.NS", "1d")

    second_bar = series.bars[1]
    assert second_bar.close == 107.0
    assert second_bar.adj_close == 106.5
    assert second_bar.close != second_bar.adj_close


def test_sorts_and_deduplicates_by_date_keeping_last():
    rows = SAMPLE_ROWS + [
        {"date": "2026-01-02", "open": 999.0, "high": 999.0, "low": 999.0, "close": 999.0, "adj_close": 999.0, "volume": 1}
    ]
    df = _make_multiindex_df(rows)
    # out of chronological order, but the duplicate for 2026-01-02 is still
    # the LAST row in provider order, so it should win
    df = df.iloc[[1, 0, 2]]

    series = normalize_yfinance_history(df, "RELIANCE.NS", "1d")

    assert [b.date for b in series.bars] == [date(2026, 1, 2), date(2026, 1, 3)]
    # the later (duplicate) row for 2026-01-02 wins
    assert series.bars[0].close == 999.0


def test_missing_expected_column_raises_malformed_error():
    df = _make_multiindex_df(SAMPLE_ROWS)
    df = df.drop(columns=[("Volume", "RELIANCE.NS")])

    with pytest.raises(MalformedProviderResponseError):
        normalize_yfinance_history(df, "RELIANCE.NS", "1d")


def test_empty_dataframe_raises_malformed_error():
    with pytest.raises(MalformedProviderResponseError):
        normalize_yfinance_history(pd.DataFrame(), "RELIANCE.NS", "1d")


# Regression: pd.Timestamp(NaT).date() does not raise — it silently returns
# NaT itself, which could otherwise let an invalid date reach OHLCVBar.
def test_valid_timestamp_index_produces_correct_python_date():
    df = _make_multiindex_df(SAMPLE_ROWS)
    series = normalize_yfinance_history(df, "RELIANCE.NS", "1d")
    assert series.bars[0].date == date(2026, 1, 2)
    assert type(series.bars[0].date) is date


def test_nat_date_index_raises_malformed_error_explicitly():
    rows = [
        {"date": "2026-01-02", "open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0, "adj_close": 104.0, "volume": 1000},
        {"date": None, "open": 104.0, "high": 108.0, "low": 103.0, "close": 107.0, "adj_close": 106.5, "volume": 1500},
    ]
    df = _make_multiindex_df(rows)
    assert pd.isna(df.index[1])  # confirm the fixture genuinely produced NaT

    with pytest.raises(MalformedProviderResponseError):
        normalize_yfinance_history(df, "RELIANCE.NS", "1d")


def test_normalized_result_never_contains_nat_dates():
    df = _make_multiindex_df(SAMPLE_ROWS)
    series = normalize_yfinance_history(df, "RELIANCE.NS", "1d")
    assert all(not pd.isna(bar.date) for bar in series.bars)
    assert all(isinstance(bar.date, date) for bar in series.bars)


# Regression: int(volume) can raise a raw Python conversion exception
# (OverflowError for +/-inf, ValueError for NaN) that must never escape
# normalize_yfinance_history as anything other than
# MalformedProviderResponseError.
@pytest.mark.parametrize("bad_volume", [float("inf"), float("-inf"), float("nan")])
def test_non_finite_volume_raises_malformed_error_not_raw_conversion_exception(bad_volume):
    rows = [
        {"date": "2026-01-02", "open": 100.0, "high": 105.0, "low": 99.0, "close": 104.0,
         "adj_close": 104.0, "volume": bad_volume},
    ]
    df = _make_multiindex_df(rows)

    with pytest.raises(MalformedProviderResponseError):
        normalize_yfinance_history(df, "RELIANCE.NS", "1d")
