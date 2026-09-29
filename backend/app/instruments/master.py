"""Local NSE instrument master: search/resolve without hitting any network.

Refresh strategy (approved, Phase 1A): refreshing the snapshot is an explicit,
manually/externally triggered operation (`refresh()`), never performed
automatically at request time or app startup. The local snapshot file is the
only thing consulted for search/resolve. For daily-bar use cases, a snapshot
refreshed periodically (e.g. weekly) is more than sufficient — the NSE equity
list changes far less often than daily prices.
"""

from __future__ import annotations

import json
from datetime import date as Date
from pathlib import Path
from typing import Callable, Optional

from app.core.exceptions import InstrumentNotFoundError
from app.instruments.models import Instrument
from app.instruments.nse_source import fetch_nse_equity_csv, parse_nse_equity_csv

_SNAPSHOT_FILENAME = "nse_equity_master.csv"
_SNAPSHOT_META_FILENAME = "nse_equity_master.meta.json"


class InstrumentMaster:
    def __init__(self, base_dir: Path):
        self._base_dir = base_dir
        self._by_symbol: dict[str, Instrument] = {}
        self._loaded = False

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
        """
        csv_text = fetch_fn()
        instruments = parse_nse_equity_csv(csv_text)

        self._base_dir.mkdir(parents=True, exist_ok=True)
        (self._base_dir / _SNAPSHOT_FILENAME).write_text(csv_text, encoding="utf-8")
        (self._base_dir / _SNAPSHOT_META_FILENAME).write_text(
            json.dumps({"refreshed_at": (today or Date.today()).isoformat(), "count": len(instruments)})
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
        if not self._loaded:
            self.load()
