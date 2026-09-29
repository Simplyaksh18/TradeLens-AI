"""Indicator orchestration: the single entry point Phase 1D should call.

Enforces the Phase 1C input boundary — indicators are only computed on data
that has passed Phase 1B validation — by re-using `validate_ohlcv_series`
rather than duplicating any of its checks.
"""

from __future__ import annotations

from app.core.exceptions import IndicatorInputInvalidError
from app.indicators.models import IndicatorRow, IndicatorSeries
from app.indicators.rsi import rsi_wilder
from app.indicators.sma import sma
from app.indicators.volume import rolling_average_volume, volume_ratio
from app.market_data.models import OHLCVSeries
from app.market_data.validation.validator import validate_ohlcv_series

SMA_SHORT_WINDOW = 20
SMA_LONG_WINDOW = 50
RSI_PERIOD = 14
VOLUME_WINDOW = 20


def compute_indicators(series: OHLCVSeries) -> IndicatorSeries:
    """Compute SMA20, SMA50, Wilder RSI14, rolling average volume, and
    volume ratio for a normalized OHLCV series.

    Raises IndicatorInputInvalidError if the series fails Phase 1B
    data-quality validation (ERROR-severity issues present). Does not
    mutate `series`.
    """
    report = validate_ohlcv_series(series)
    if not report.is_valid:
        raise IndicatorInputInvalidError(series.provider_symbol, report.error_count)

    closes = [bar.close for bar in series.bars]
    volumes = [bar.volume for bar in series.bars]

    sma20_values = sma(closes, SMA_SHORT_WINDOW)
    sma50_values = sma(closes, SMA_LONG_WINDOW)
    rsi14_values = rsi_wilder(closes, RSI_PERIOD)
    average_volume_values = rolling_average_volume(volumes, VOLUME_WINDOW)
    volume_ratio_values = volume_ratio(volumes, VOLUME_WINDOW)

    rows = tuple(
        IndicatorRow(
            date=bar.date,
            sma20=sma20_values[i],
            sma50=sma50_values[i],
            rsi14=rsi14_values[i],
            average_volume=average_volume_values[i],
            volume_ratio=volume_ratio_values[i],
        )
        for i, bar in enumerate(series.bars)
    )

    return IndicatorSeries(provider_symbol=series.provider_symbol, interval=series.interval, rows=rows)
