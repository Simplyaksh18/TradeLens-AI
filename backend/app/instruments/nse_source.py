"""Source of the NSE equity instrument universe.

Source: NSE's own published bulk listing file (`EQUITY_L.csv` from
archives.nseindia.com) — the standard authoritative snapshot of all
main-board NSE equities. Chosen over per-symbol Yahoo queries (explicitly
disallowed) and over third-party wrapper libraries (unnecessary dependency
for what is just a CSV fetch+parse).

Verified during Phase 1A design (2026-09-26): a plain HTTPS GET with a
browser-like User-Agent succeeds without needing nseindia.com's cookie
handshake (that handshake is needed for its JSON APIs, not this static
archive file). ~2500 rows, refreshed by NSE periodically.

This module only fetches and parses. Refresh cadence and local snapshot
persistence are InstrumentMaster's responsibility (instruments/master.py) —
instrument discovery is intentionally decoupled from historical-price
retrieval per the Phase 1A requirement.
"""

from __future__ import annotations

import io

import pandas as pd
import requests

from app.instruments.models import (
    Exchange,
    Instrument,
    InstrumentStatus,
    InstrumentType,
)
from app.market_data.providers.yfinance_symbol import to_yfinance_symbol

NSE_EQUITY_LIST_URL = "https://archives.nseindia.com/content/equities/EQUITY_L.csv"

# NSE blocks requests without a browser-like User-Agent; verified necessary
# and sufficient for this static archive endpoint (no cookies/session needed).
_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def fetch_nse_equity_csv(timeout_seconds: float = 15.0) -> str:
    """Fetch the raw EQUITY_L.csv text. One request; no retries.

    Raises requests.exceptions.RequestException on any network/HTTP failure —
    callers (InstrumentMaster.refresh) decide how to surface that.
    """
    response = requests.get(NSE_EQUITY_LIST_URL, headers=_REQUEST_HEADERS, timeout=timeout_seconds)
    response.raise_for_status()
    return response.text


def parse_nse_equity_csv(csv_text: str) -> list[Instrument]:
    """Parse EQUITY_L.csv text into Instrument records.

    All rows in this file are NSE main-board equities; presence in the
    current snapshot is treated as the instrument being active (delisted
    equities are removed from NSE's published list, not flagged inline).
    """
    df = pd.read_csv(io.StringIO(csv_text), skipinitialspace=True)
    df.columns = [c.strip() for c in df.columns]

    instruments: list[Instrument] = []
    for row in df.to_dict(orient="records"):
        symbol = str(row["SYMBOL"]).strip().upper()
        name = str(row["NAME OF COMPANY"]).strip()
        isin = str(row.get("ISIN NUMBER", "")).strip() or None
        series = str(row.get("SERIES", "")).strip() or None

        instruments.append(
            Instrument(
                symbol=symbol,
                exchange=Exchange.NSE,
                name=name,
                provider_symbol=to_yfinance_symbol(symbol),
                instrument_type=InstrumentType.EQUITY,
                status=InstrumentStatus.ACTIVE,
                isin=isin,
                series=series,
            )
        )
    return instruments
