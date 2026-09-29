"""Application-level historical-data cache.

Design (Phase 1A, approved scope — see CLAUDE.md "do not prematurely build
sophisticated cache invalidation"):

  - One Parquet file per (provider, provider_symbol, interval), holding ALL
    bars ever fetched for that key, deduplicated by date. This lets an
    overlapping/sub-range request be served without re-hitting the provider,
    per the success criteria in the task (RELIANCE 2024 sub-range of a
    cached 2020-2025 range must not call yfinance).
  - A small JSON sidecar (`*.meta.json`) tracks the cached coverage
    (min/max date) and `last_refreshed` so `compute_missing_ranges` can
    decide what (if anything) needs fetching, without loading the Parquet
    file just to answer a coverage question.

Freshness policy for daily bars (documented, simple, Phase-1-appropriate):
  - Bars strictly before `last_refreshed`'s date are treated as final and are
    never silently re-fetched.
  - If the cache was NOT refreshed today and the caller's requested range
    extends past the cached end date, we re-fetch starting a few calendar
    days before the cached end date (see `_REFRESH_OVERLAP_DAYS`) through the
    requested end date. This overlap re-pulls the last few bars in case a
    corporate action revised their adjusted close since the last refresh,
    without re-pulling the whole series. It does not, and cannot, detect a
    revision to older bars — that is out of scope for Phase 1.
  - We never forward-fill or interpolate: a Parquet file only ever contains
    bars the provider actually returned.

Concurrency (Phase 1E note, since FastAPI may serve requests concurrently):
`HistoricalDataCache` itself holds no in-memory state — every operation
reads/writes the filesystem directly. Writes use a temp-file-then-
`os.replace()` pattern (see `_atomic_write_parquet`/`_atomic_write_text`).
That alone is enough on POSIX, but a concurrency test surfaced a genuine
Windows-specific defect: Windows raises `PermissionError` from
`os.replace()` if the destination file is concurrently open for reading by
another thread (POSIX permits renaming over an open handle; Windows does
not). Fixed with a per-`(provider, symbol, interval)` `threading.Lock`
(`_lock_for`) guarding BOTH `read_range`/`load_meta` and `merge_and_write`'s
file I/O — a reader can never have the file open while a writer replaces
it. Different keys still run fully in parallel; only same-key file I/O is
serialized. The provider network call in `MarketDataService.get_history`
happens OUTSIDE this lock, so two concurrent cache-miss requests for the
same key can still both call the provider (a redundant-fetch inefficiency,
not a correctness defect) — accepted per the Phase 1E "do not
over-synchronize" guidance; only file corruption/torn reads needed fixing.
"""

from __future__ import annotations

import json
import os
import threading
import uuid
from dataclasses import dataclass
from datetime import date as Date
from datetime import timedelta
from pathlib import Path
from typing import Optional

import pandas as pd

from app.market_data.models import OHLCVBar, OHLCVSeries

_REFRESH_OVERLAP_DAYS = 5


@dataclass(frozen=True)
class CacheMeta:
    start_date: Date
    end_date: Date
    last_refreshed: Date


def compute_missing_ranges(
    requested_start: Date,
    requested_end: Date,
    cached_meta: Optional[CacheMeta],
    today: Date,
) -> list[tuple[Date, Date]]:
    """Pure function: what date range(s) must be fetched from the provider.

    Returns a list of inclusive (start, end) ranges, in the order they should
    be fetched. Empty list means the cache already fully covers the request
    under the freshness policy described in this module's docstring.
    """
    if cached_meta is None:
        return [(requested_start, requested_end)]

    missing: list[tuple[Date, Date]] = []

    if requested_start < cached_meta.start_date:
        missing.append((requested_start, cached_meta.start_date - timedelta(days=1)))

    if requested_end > cached_meta.end_date:
        if cached_meta.last_refreshed < today:
            extension_start = max(
                requested_start, cached_meta.end_date - timedelta(days=_REFRESH_OVERLAP_DAYS)
            )
        else:
            extension_start = cached_meta.end_date + timedelta(days=1)
        if extension_start <= requested_end:
            missing.append((extension_start, requested_end))

    return missing


class HistoricalDataCache:
    """Parquet-backed cache of normalized OHLCV series, keyed by
    (provider name, provider symbol, interval)."""

    def __init__(self, base_dir: Path):
        self._base_dir = base_dir
        self._locks_guard = threading.Lock()
        self._locks: dict[tuple[str, str, str], threading.Lock] = {}

    def _lock_for(self, provider_name: str, provider_symbol: str, interval: str) -> threading.Lock:
        """Per-(provider, symbol, interval) lock guarding this key's file I/O.

        Windows-specific correctness note (discovered via a concurrency
        test, Phase 1E): `os.replace()` — used for the atomic writes below —
        raises `PermissionError` on Windows if the destination file is
        concurrently open for reading by another thread (POSIX allows
        renaming over an open file handle; Windows does not). A per-key lock
        around BOTH reads and writes closes this window: a reader never has
        the file open while a writer replaces it. Different keys (symbols)
        still run fully in parallel — only same-key file I/O is serialized.
        Provider network calls happen OUTSIDE this lock (see
        MarketDataService.get_history), so this does not serialize slow
        upstream fetches, only the fast local file operations.
        """
        key = (provider_name, provider_symbol, interval)
        with self._locks_guard:
            lock = self._locks.get(key)
            if lock is None:
                lock = threading.Lock()
                self._locks[key] = lock
            return lock

    def load_meta(self, provider_name: str, provider_symbol: str, interval: str) -> Optional[CacheMeta]:
        with self._lock_for(provider_name, provider_symbol, interval):
            return self._load_meta_unlocked(provider_name, provider_symbol, interval)

    def _load_meta_unlocked(self, provider_name: str, provider_symbol: str, interval: str) -> Optional[CacheMeta]:
        _, meta_path = self._paths(provider_name, provider_symbol, interval)
        if not meta_path.exists():
            return None
        raw = json.loads(meta_path.read_text())
        return CacheMeta(
            start_date=Date.fromisoformat(raw["start_date"]),
            end_date=Date.fromisoformat(raw["end_date"]),
            last_refreshed=Date.fromisoformat(raw["last_refreshed"]),
        )

    def read_range(
        self,
        provider_name: str,
        provider_symbol: str,
        interval: str,
        start_date: Date,
        end_date: Date,
    ) -> OHLCVSeries:
        with self._lock_for(provider_name, provider_symbol, interval):
            parquet_path, _ = self._paths(provider_name, provider_symbol, interval)
            if not parquet_path.exists():
                return OHLCVSeries(provider_symbol=provider_symbol, interval=interval, bars=())
            df = pd.read_parquet(parquet_path, engine="pyarrow")
            series = _dataframe_to_series(df, provider_symbol, interval)
            return series.sliced(start_date, end_date)

    def merge_and_write(
        self,
        provider_name: str,
        provider_symbol: str,
        interval: str,
        fetched: OHLCVSeries,
        queried_start: Date,
        queried_end: Date,
        today: Date,
    ) -> None:
        """Merge freshly fetched bars into the existing cache (if any) and
        update the coverage metadata. On a date collision, the freshly
        fetched bar wins (supports the adjusted-close-revision case).

        Coverage (`start_date`/`end_date`) is tracked using `queried_start`/
        `queried_end` — the date range that was actually asked of the
        provider — NOT the min/max date of the bars actually returned.
        A provider legitimately returns no bar for a weekend/holiday inside
        the queried range; using the bars' own date range as "coverage"
        would make the cache think that leading/trailing gap was never
        queried, triggering a spurious re-fetch (and a false
        no-data-for-period failure) on every subsequent identical request.
        """
        with self._lock_for(provider_name, provider_symbol, interval):
            parquet_path, meta_path = self._paths(provider_name, provider_symbol, interval)
            parquet_path.parent.mkdir(parents=True, exist_ok=True)

            existing_bars: tuple[OHLCVBar, ...] = ()
            if parquet_path.exists():
                existing_df = pd.read_parquet(parquet_path, engine="pyarrow")
                existing_bars = _dataframe_to_series(existing_df, provider_symbol, interval).bars

            by_date = {b.date: b for b in existing_bars}
            for bar in fetched.bars:
                by_date[bar.date] = bar
            merged_bars = tuple(by_date[d] for d in sorted(by_date))

            if merged_bars:
                merged_series = OHLCVSeries(provider_symbol=provider_symbol, interval=interval, bars=merged_bars)
                _atomic_write_parquet(_series_to_dataframe(merged_series), parquet_path)

            existing_meta = self._load_meta_unlocked(provider_name, provider_symbol, interval)
            new_start = queried_start
            new_end = queried_end
            if existing_meta is not None:
                new_start = min(new_start, existing_meta.start_date)
                new_end = max(new_end, existing_meta.end_date)

            _atomic_write_text(
                meta_path,
                json.dumps(
                    {
                        "start_date": new_start.isoformat(),
                        "end_date": new_end.isoformat(),
                        "last_refreshed": today.isoformat(),
                    }
                ),
            )

    def _paths(self, provider_name: str, provider_symbol: str, interval: str) -> tuple[Path, Path]:
        safe_symbol = provider_symbol.replace(".", "_")
        stem = self._base_dir / provider_name / f"{safe_symbol}_{interval}"
        return stem.with_suffix(".parquet"), stem.with_suffix(".meta.json")


def _atomic_write_parquet(df: pd.DataFrame, final_path: Path) -> None:
    """Write via a temp file in the same directory + os.replace, so a
    concurrent reader (Phase 1E: concurrent HTTP requests) never observes a
    partially-written Parquet file, and two concurrent writers never
    interleave into a corrupted one. os.replace is atomic on the same
    filesystem on both POSIX and Windows.

    This does NOT prevent two concurrent cache-miss requests from both
    calling the provider (a redundant-fetch inefficiency, not a correctness
    defect — see HistoricalDataCache's module docstring / CLAUDE.md Phase 1E
    concurrency notes); it only prevents file corruption/torn reads.
    """
    tmp_path = final_path.with_name(f"{final_path.name}.tmp-{uuid.uuid4().hex}")
    df.to_parquet(tmp_path, engine="pyarrow", index=False)
    os.replace(tmp_path, final_path)


def _atomic_write_text(final_path: Path, text: str, encoding: str = "utf-8") -> None:
    """Reused (not duplicated) by app.instruments.master.InstrumentMaster.refresh
    for its NSE snapshot write, for the exact same atomic-write reasoning
    documented above `_atomic_write_parquet`. `encoding` defaults to "utf-8"
    (this module's own meta-JSON callers are ASCII-safe either way; the CSV
    snapshot is not, since NSE company names may contain non-ASCII
    characters -- explicit utf-8 avoids depending on the platform's default
    text encoding, which is NOT utf-8 on Windows)."""
    tmp_path = final_path.with_name(f"{final_path.name}.tmp-{uuid.uuid4().hex}")
    tmp_path.write_text(text, encoding=encoding)
    os.replace(tmp_path, final_path)


def _series_to_dataframe(series: OHLCVSeries) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "date": [b.date.isoformat() for b in series.bars],
            "open": [b.open for b in series.bars],
            "high": [b.high for b in series.bars],
            "low": [b.low for b in series.bars],
            "close": [b.close for b in series.bars],
            "adj_close": [b.adj_close for b in series.bars],
            "volume": [b.volume for b in series.bars],
        }
    )


def _dataframe_to_series(df: pd.DataFrame, provider_symbol: str, interval: str) -> OHLCVSeries:
    bars = tuple(
        OHLCVBar(
            date=Date.fromisoformat(row.date),
            open=float(row.open),
            high=float(row.high),
            low=float(row.low),
            close=float(row.close),
            adj_close=None if pd.isna(row.adj_close) else float(row.adj_close),
            volume=int(row.volume),
        )
        for row in df.itertuples(index=False)
    )
    return OHLCVSeries(provider_symbol=provider_symbol, interval=interval, bars=bars)
