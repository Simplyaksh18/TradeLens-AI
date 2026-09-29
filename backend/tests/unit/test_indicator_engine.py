import copy
from datetime import date, timedelta

import pytest

from app.core.exceptions import IndicatorInputInvalidError
from app.indicators.engine import compute_indicators
from app.market_data.models import OHLCVBar, OHLCVSeries


def _make_series(n=60, start=date(2024, 1, 1)):
    bars = []
    close = 100.0
    for i in range(n):
        close += 1.0 if i % 2 == 0 else -0.5  # varying, non-monotonic prices
        d = start + timedelta(days=i)
        bars.append(
            OHLCVBar(date=d, open=close - 1, high=close + 2, low=close - 2, close=close,
                     adj_close=close, volume=1000 + i)
        )
    return OHLCVSeries(provider_symbol="RELIANCE.NS", interval="1d", bars=tuple(bars))


def test_output_length_and_date_alignment():
    series = _make_series(n=60)
    result = compute_indicators(series)

    assert len(result.rows) == 60
    assert [r.date for r in result.rows] == [b.date for b in series.bars]
    assert result.provider_symbol == "RELIANCE.NS"
    assert result.interval == "1d"


def test_warm_up_alignment_across_all_indicators():
    series = _make_series(n=60)
    result = compute_indicators(series)

    assert all(r.sma20 is None for r in result.rows[:19])
    assert result.rows[19].sma20 is not None

    assert all(r.sma50 is None for r in result.rows[:49])
    assert result.rows[49].sma50 is not None

    assert all(r.rsi14 is None for r in result.rows[:14])
    assert result.rows[14].rsi14 is not None

    assert all(r.average_volume is None for r in result.rows[:20])
    assert result.rows[20].average_volume is not None

    assert all(r.volume_ratio is None for r in result.rows[:20])
    assert result.rows[20].volume_ratio is not None


def test_invalid_series_raises_indicator_input_invalid_error():
    d = date(2024, 1, 1)
    bad_bar = OHLCVBar(date=d, open=100, high=90, low=95, close=105, adj_close=100, volume=500)
    series = OHLCVSeries(provider_symbol="X.NS", interval="1d", bars=(bad_bar,))

    with pytest.raises(IndicatorInputInvalidError):
        compute_indicators(series)


def test_does_not_mutate_input_series():
    series = _make_series(n=25)
    snapshot = copy.deepcopy(series)

    compute_indicators(series)

    assert series == snapshot


def test_no_look_ahead_end_to_end():
    series = _make_series(n=60)
    result_before = compute_indicators(series)

    extra_bars = list(series.bars) + [
        OHLCVBar(date=series.bars[-1].date + timedelta(days=i + 1),
                 open=9999, high=10000, low=9000, close=9999, adj_close=9999, volume=999999)
        for i in range(5)
    ]
    extended_series = OHLCVSeries(provider_symbol="RELIANCE.NS", interval="1d", bars=tuple(extra_bars))
    result_after = compute_indicators(extended_series)

    for i in range(len(series.bars)):
        row_before = result_before.rows[i]
        row_after = result_after.rows[i]
        assert row_before == row_after
