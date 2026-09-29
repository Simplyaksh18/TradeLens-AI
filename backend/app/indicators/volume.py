"""Rolling average volume and volume ratio.

Approved definition (Phase 1C, given — not chosen here):
  rolling average volume at T = mean of the PREVIOUS 20 completed bars,
  EXCLUDING the current bar T.
  volume_ratio at T = Volume[T] / that previous-20-bar average.

This denominator choice (prior bars only, current excluded) is deliberate:
the feature answers "is today's volume unusual relative to recent history",
which requires comparing against a baseline that does not already include
today's own value.

Zero-denominator convention: if the previous-20-bar average is exactly 0.0
(e.g. an illiquid instrument with 20 consecutive zero-volume days — legal
under Phase 1B's zero-volume WARNING policy), volume_ratio is `None`
(unavailable) rather than `inf` or a fabricated value.
"""

from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd

_DEFAULT_WINDOW = 20


def rolling_average_volume(volumes: Sequence[float], window: int = _DEFAULT_WINDOW) -> list[Optional[float]]:
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")

    series = pd.Series(list(volumes), dtype=float)
    previous_bars_only = series.shift(1)  # excludes the current bar
    rolling_mean = previous_bars_only.rolling(window=window, min_periods=window).mean()
    return [None if pd.isna(v) else float(v) for v in rolling_mean]


def volume_ratio(volumes: Sequence[float], window: int = _DEFAULT_WINDOW) -> list[Optional[float]]:
    averages = rolling_average_volume(volumes, window)
    ratios: list[Optional[float]] = []
    for current_volume, average in zip(volumes, averages):
        if average is None or average == 0.0:
            ratios.append(None)
        else:
            ratios.append(float(current_volume) / average)
    return ratios
