"""Generic Simple Moving Average.

For window N, SMA at index t is the arithmetic mean of the N most recent
values including t (i.e. values at [t-N+1, t]). Undefined until N
observations exist — no backfill, no look-ahead (pandas `rolling` only ever
looks at the current and past positions).
"""

from __future__ import annotations

from typing import Optional, Sequence

import pandas as pd


def sma(values: Sequence[float], window: int) -> list[Optional[float]]:
    if window < 1:
        raise ValueError(f"window must be >= 1, got {window}")

    series = pd.Series(list(values), dtype=float)
    rolling_mean = series.rolling(window=window, min_periods=window).mean()
    return [None if pd.isna(v) else float(v) for v in rolling_mean]
