"""Local NSE instrument master: search/resolve without hitting any network.

Refresh strategy (approved, Phase 1A): refreshing the snapshot is an explicit,
manually/externally triggered operation (`refresh()`), never performed
automatically at request time or app startup. The local snapshot file is the
only thing consulted for search/resolve. For daily-bar use cases, a snapshot
refreshed periodically (e.g. weekly) is more than sufficient — the NSE equity
list changes far less often than daily prices.

Clean-deploy bootstrap (deployment-compatibility addition, see CLAUDE.md):
the rule above assumes a snapshot exists SOMEWHERE on disk already (true for
local dev and for Docker Compose's bind-mounted `./data`, both of which
retain whatever a developer's one-off manual `refresh()` produced). A fresh
production filesystem (e.g. Render, ephemeral, no persistent disk) that has
NEVER had `refresh()` run against it has no snapshot to load at all, and no
human has shell access to run one. `_ensure_loaded` below handles exactly
this one case automatically — see its docstring — while leaving the
explicit/manual refresh contract for an EXISTING (possibly stale) snapshot
completely unchanged: this module still never re-fetches merely because a
snapshot is old, only because it is entirely absent.
"""

from __future__ import annotations

import json
import threading
from datetime import date as Date
from pathlib import Path
from typing import Callable, Optional

from app.core.exceptions import InstrumentCatalogUnavailableError, InstrumentNotFoundError
from app.instruments.models import Instrument
from app.instruments.nse_source import fetch_nse_equity_csv, parse_nse_equity_csv
from app.market_data.cache import _atomic_write_text

_SNAPSHOT_FILENAME = "nse_equity_master.csv"
_SNAPSHOT_META_FILENAME = "nse_equity_master.meta.json"


class InstrumentMaster:
    def __init__(self, base_dir: Path):
        self._base_dir = base_dir
        self._by_symbol: dict[str, Instrument] = {}
        self._loaded = False
        # Guards the clean-deploy bootstrap path only (see _ensure_loaded) --
        # NOT ordinary load()/search()/resolve() calls, which stay lock-free
        # exactly as before (redundant concurrent re-parses of an existing
        # snapshot remain harmless, per the existing Phase 1E concurrency
        # review in app/api/dependencies.py). Threading-level only: this
        # process runs as a single Uvicorn worker (see backend/Dockerfile),
        # so a thread lock is sufficient here, unlike a genuinely
        # multi-process deployment which would need a cross-process lock.
        self._bootstrap_lock = threading.Lock()

    def refresh(
        self,
        today: Optional[Date] = None,
        fetch_fn: Callable[[], str] = fetch_nse_equity_csv,
    ) -> int:
        """Fetch the current NSE equity list and persist it as the local
        snapshot. Returns the number of instruments loaded.

        One network request. No retries — a failure here should be surfaced,
        not masked, since it means the instrument master could not be
        updated (the previous snapshot, if any, remains on disk untouched).

        Writes are atomic (temp file + os.replace, reusing the exact helper
        HistoricalDataCache already established for this same reason -- see
        app/market_data/cache.py) so a reader never observes a
        partially-written snapshot and two concurrent refreshes never
        interleave into a corrupted file.
        """
        csv_text = fetch_fn()
        instruments = parse_nse_equity_csv(csv_text)

        self._base_dir.mkdir(parents=True, exist_ok=True)
        _atomic_write_text(self._base_dir / _SNAPSHOT_FILENAME, csv_text)
        _atomic_write_text(
            self._base_dir / _SNAPSHOT_META_FILENAME,
            json.dumps({"refreshed_at": (today or Date.today()).isoformat(), "count": len(instruments)}),
        )

        self._by_symbol = {inst.symbol: inst for inst in instruments}
        self._loaded = True
        return len(instruments)

    def load(self) -> int:
        """Load the local snapshot from disk into memory. Does not touch the network.

        Raises FileNotFoundError if `refresh()` has never been run.
        """
        snapshot_path = self._base_dir / _SNAPSHOT_FILENAME
        if not snapshot_path.exists():
            raise FileNotFoundError(
                f"No instrument master snapshot at {snapshot_path}. Call refresh() first."
            )
        instruments = parse_nse_equity_csv(snapshot_path.read_text(encoding="utf-8"))
        self._by_symbol = {inst.symbol: inst for inst in instruments}
        self._loaded = True
        return len(instruments)

    def resolve(self, symbol: str) -> Instrument:
        """Exact-symbol lookup (case-insensitive). Raises InstrumentNotFoundError."""
        self._ensure_loaded()
        instrument = self._by_symbol.get(symbol.strip().upper())
        if instrument is None:
            raise InstrumentNotFoundError(symbol)
        return instrument

    def search(self, query: str, limit: int = 20) -> list[Instrument]:
        """Case-insensitive substring search over symbol and company name."""
        self._ensure_loaded()
        needle = query.strip().upper()
        if not needle:
            return []
        matches = [
            inst
            for inst in self._by_symbol.values()
            if needle in inst.symbol or needle in inst.name.upper()
        ]
        return matches[:limit]

    def _ensure_loaded(self) -> None:
        if self._loaded:
            return
        with self._bootstrap_lock:
            if self._loaded:  # another thread may have finished while we waited
                return
            try:
                self.load()
            except FileNotFoundError:
                self._bootstrap()

    def _bootstrap(self) -> None:
        """Clean-deploy bootstrap: the local snapshot has NEVER been
        generated on this filesystem (see module docstring). This is the
        ONLY situation `refresh()` is ever triggered automatically -- once
        it succeeds, the snapshot exists on disk and every subsequent
        `_ensure_loaded()` call (this process or a future one, as long as
        the file persists) takes the normal `load()` path above instead.
        Always called while holding `_bootstrap_lock`, so concurrent
        first-requests trigger at most one NSE fetch, not one per request.

        Global and symbol-agnostic: this bootstraps the ENTIRE catalogue via
        the existing, accepted `refresh()`/NSE-source mechanism -- there is
        no per-symbol code path anywhere in this class.

        Never fabricates instruments. If the fetch, parse, or write fails
        for any reason, that failure is reported as a controlled
        InstrumentCatalogUnavailableError (never a hardcoded fallback list,
        never a raw FileNotFoundError/network-exception leaking past this
        boundary) -- the original exception is preserved via `__cause__`.
        """
        try:
            self.refresh()
        except Exception as exc:
            raise InstrumentCatalogUnavailableError() from exc
