"""Live network integration test against archives.nseindia.com.
Excluded from the default run; see test_yfinance_provider_live.py header.
Makes exactly one real request.
"""

import pytest

from app.instruments.nse_source import fetch_nse_equity_csv, parse_nse_equity_csv


@pytest.mark.integration
def test_live_fetch_and_parse_nse_equity_list():
    csv_text = fetch_nse_equity_csv()
    instruments = parse_nse_equity_csv(csv_text)

    assert len(instruments) > 1000  # NSE lists thousands of equities
    symbols = {i.symbol for i in instruments}
    assert "RELIANCE" in symbols
    assert "INFY" in symbols
