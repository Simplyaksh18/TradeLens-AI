"""yfinance-specific symbol-mapping convention.

Isolated in its own module (rather than inline in instrument ingestion) so
the ".NS" suffix convention — a yfinance-specific detail, not a TradeLens or
NSE concept — stays inside the provider package.
"""

from __future__ import annotations

_NSE_YFINANCE_SUFFIX = ".NS"


def to_yfinance_symbol(nse_symbol: str) -> str:
    """Map a bare NSE trading symbol (e.g. "TATASTEEL") to its yfinance
    ticker (e.g. "TATASTEEL.NS").

    Assumption: NSE main-board equities are addressable on yfinance via the
    ".NS" suffix. This holds for all symbols observed in the Phase 1.0 POC
    and is yfinance's documented convention for NSE.
    """
    symbol = nse_symbol.strip().upper()
    return f"{symbol}{_NSE_YFINANCE_SUFFIX}"
