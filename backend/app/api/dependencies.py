"""Centralized dependency wiring.

Concurrency / shared-state classification (Phase 1E, inspected — see
CLAUDE.md for the full write-up):

  - InstrumentMaster: mutable (`_by_symbol`, `_loaded`), lazily loads its
    snapshot from a LOCAL file on first search/resolve call — no network.
    Classified SHARED/READ-MOSTLY: after the first lazy load, all access is
    read-only. Two concurrent first-requests could both run `load()`
    concurrently; both just re-parse the same on-disk snapshot and assign an
    equivalent `_by_symbol` dict — redundant work, not corruption (CPython
    attribute assignment is atomic; the file itself isn't written by
    `load()`). No lock added.
  - HistoricalDataCache: holds NO in-memory state; every call reads/writes
    the filesystem directly. Classified SHARED, and DID need a fix — see
    `app/market_data/cache.py`'s module docstring (atomic temp-file +
    `os.replace()` writes, added this phase) to prevent a torn read or a
    corrupted file if two requests race for the same cache key. Duplicate
    provider fetches on a simultaneous cache miss remain possible but are a
    performance concern, not a correctness one.
  - YFinanceProvider: holds no TradeLens-level state; each call is an
    independent `yf.download`. Classified SHARED/STATELESS from TradeLens's
    perspective (yfinance's own internal session/cookie handling is outside
    this codebase's control and out of scope here).
  - MarketDataService: pure composition (provider + cache + instrument
    master references only), no state of its own. SHARED/STATELESS.

None of the above perform network or file I/O in `__init__`, so building
these dependencies has no import-time or startup-time side effects.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from functools import lru_cache
from math import isfinite
from pathlib import Path

from fastapi import Depends, Query

from app.agent.dependencies import AgentDependencies, build_agent_dependencies
from app.agent.provider import GroqToolCallingLanguageModel, ToolCallingLanguageModel
from app.api.errors import RequestContractError
from app.instruments.master import InstrumentMaster
from app.market_data.cache import HistoricalDataCache
from app.market_data.providers.yfinance_provider import YFinanceProvider
from app.market_data.service import MarketDataService

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_INSTRUMENT_MASTER_DIR = _PROJECT_ROOT / "data" / "instrument_master"
_MARKET_DATA_CACHE_DIR = _PROJECT_ROOT / "data" / "market_data_cache"

SUPPORTED_INTERVALS = {"1d"}
MAX_HISTORY_SPAN_DAYS = 365 * 5


@lru_cache
def get_instrument_master() -> InstrumentMaster:
    return InstrumentMaster(_INSTRUMENT_MASTER_DIR)


@lru_cache
def get_cache() -> HistoricalDataCache:
    return HistoricalDataCache(_MARKET_DATA_CACHE_DIR)


@lru_cache
def get_provider() -> YFinanceProvider:
    return YFinanceProvider()


def get_market_data_service(
    provider: YFinanceProvider = Depends(get_provider),
    cache: HistoricalDataCache = Depends(get_cache),
    instrument_master: InstrumentMaster = Depends(get_instrument_master),
) -> MarketDataService:
    return MarketDataService(provider, cache, instrument_master)


# Phase 5E: built once per process (lru_cache), not per request -- the
# Phase 5A knowledge index (`ResearchKnowledgeRetriever.index_corpus()`,
# called inside `build_agent_dependencies()`) is static, offline, local
# reference documentation with no per-request state, so re-indexing it on
# every research request would be pure repeated work with no benefit
# (see CLAUDE.md Phase 5E dependency-lifecycle note). No Redis/Celery/
# service container was introduced -- `lru_cache` is the same pattern
# already used for `get_instrument_master`/`get_cache`/`get_provider`
# above. `GroqToolCallingLanguageModel()` construction is cheap and lazy
# (no GROQ_API_KEY read until a request actually calls `generate_step`),
# matching the accepted Phase 5B/5C provider-construction contract.
@lru_cache
def get_agent_dependencies() -> AgentDependencies:
    return build_agent_dependencies()


@lru_cache
def get_tool_calling_provider() -> ToolCallingLanguageModel:
    return GroqToolCallingLanguageModel()


@dataclass(frozen=True)
class HistoryQueryParams:
    start: Date
    end: Date
    interval: str


def history_query_params(
    start: Date = Query(..., description="Inclusive start date (YYYY-MM-DD)"),
    end: Date = Query(..., description="Inclusive end date (YYYY-MM-DD)"),
    interval: str = Query("1d", description="Bar interval; only '1d' is currently supported"),
) -> HistoryQueryParams:
    if interval not in SUPPORTED_INTERVALS:
        raise RequestContractError(
            "UNSUPPORTED_INTERVAL",
            f"Unsupported interval {interval!r}; supported: {sorted(SUPPORTED_INTERVALS)}.",
        )
    if start > end:
        raise RequestContractError("INVALID_DATE_RANGE", "start must be <= end.")
    if (end - start).days > MAX_HISTORY_SPAN_DAYS:
        raise RequestContractError(
            "DATE_RANGE_TOO_LARGE",
            f"Requested span exceeds the maximum of {MAX_HISTORY_SPAN_DAYS} days.",
        )
    return HistoryQueryParams(start=start, end=end, interval=interval)


DEFAULT_INITIAL_CAPITAL = 100_000.0


@dataclass(frozen=True)
class BacktestQueryParams:
    initial_capital: float


def backtest_query_params(
    initial_capital: float = Query(DEFAULT_INITIAL_CAPITAL, description="Starting cash for the Phase 2B backtest; must be finite and > 0."),
) -> BacktestQueryParams:
    # Phase 2B V1 has no cost/slippage parameters exposed here -- the
    # domain layer rejects any nonzero value (see BacktestConfig), so
    # there is nothing meaningful for the API to accept from the caller.
    if not isfinite(initial_capital) or initial_capital <= 0:
        raise RequestContractError("INVALID_INITIAL_CAPITAL", "initial_capital must be finite and > 0.")
    return BacktestQueryParams(initial_capital=initial_capital)
