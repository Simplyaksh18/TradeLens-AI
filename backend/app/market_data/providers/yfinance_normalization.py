"""Pure normalization of a yfinance historical-data DataFrame into TradeLens's
provider-independent OHLCVSeries.

Kept separate from yfinance_provider.py so it can be unit tested with
constructed DataFrame fixtures, without calling yfinance or the network.

Assumes the caller already handled the "empty result" case (normalization
requires a non-empty DataFrame — see yfinance_provider.py).
"""

from __future__ import annotations

import math

import pandas as pd

from app.core.exceptions import MalformedProviderResponseError
from app.market_data.models import OHLCVBar, OHLCVSeries

_COLUMN_MAP = {
    "Open": "open",
    "High": "high",
    "Low": "low",
    "Close": "close",
    "Adj Close": "adj_close",
    "Volume": "volume",
}

# auto_adjust=False (TradeLens's chosen ingestion policy) yields all of these.
_REQUIRED_YFINANCE_COLUMNS = {"Open", "High", "Low", "Close", "Adj Close", "Volume"}


def normalize_yfinance_history(
    df: pd.DataFrame,
    provider_symbol: str,
    interval: str,
) -> OHLCVSeries:
    """Convert a raw yfinance `download`/`history` DataFrame into an OHLCVSeries.

    Handles both the MultiIndex columns yfinance returns for `download()`
    (even for a single ticker) and plain flat columns, for robustness against
    minor yfinance version differences.
    """
    if df.empty:
        raise MalformedProviderResponseError(
            f"normalize_yfinance_history called with an empty DataFrame for "
            f"{provider_symbol!r}; emptiness must be handled by the caller "
            "before normalization."
        )

    working = df.copy()
    if isinstance(working.columns, pd.MultiIndex):
        working.columns = working.columns.get_level_values(0)

    missing_columns = _REQUIRED_YFINANCE_COLUMNS - set(working.columns)
    if missing_columns:
        raise MalformedProviderResponseError(
            f"yfinance response for {provider_symbol!r} is missing expected "
            f"columns {sorted(missing_columns)}; got {list(working.columns)}"
        )

    working = working.rename(columns=_COLUMN_MAP)

    bars: list[OHLCVBar] = []
    try:
        for row in working.itertuples(index=True, name="RawBar"):
            timestamp = pd.Timestamp(row.Index)
            if pd.isna(timestamp):
                # pd.Timestamp(NaT).date() does not raise — it silently
                # returns NaT itself, which would otherwise let an invalid
                # date reach OHLCVBar. Must fail explicitly instead.
                raise MalformedProviderResponseError(
                    f"yfinance response for {provider_symbol!r} has a missing/NaT "
                    f"date at row index {row.Index!r}"
                )
            bar_date = timestamp.date()
            adj_close = None if _is_nan(row.adj_close) else float(row.adj_close)
            bars.append(
                OHLCVBar(
                    date=bar_date,
                    open=float(row.open),
                    high=float(row.high),
                    low=float(row.low),
                    close=float(row.close),
                    adj_close=adj_close,
                    volume=int(row.volume),
                )
            )
    except (ValueError, TypeError, OverflowError) as exc:
        raise MalformedProviderResponseError(
            f"Could not convert a yfinance row to OHLCVBar for {provider_symbol!r}: {exc}"
        ) from exc

    deduplicated = _drop_duplicate_dates(bars)
    deduplicated.sort(key=lambda b: b.date)

    return OHLCVSeries(
        provider_symbol=provider_symbol,
        interval=interval,
        bars=tuple(deduplicated),
    )


def _is_nan(value) -> bool:
    try:
        return math.isnan(value)
    except TypeError:
        return False


def _drop_duplicate_dates(bars: list[OHLCVBar]) -> list[OHLCVBar]:
    """Keep the last bar for any duplicate date, in the provider's original
    row order (not yet sorted by date at this point)."""
    by_date: dict = {}
    for bar in bars:
        by_date[bar.date] = bar
    return list(by_date.values())
