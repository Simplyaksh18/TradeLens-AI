"""Live network integration test. Excluded from the default test run
(see pytest.ini `addopts = -m "not integration"`). Run explicitly with:

    pytest -m integration

Makes exactly one real request to Yahoo Finance. Do not add more symbols or
loops here — this is a smoke test that the provider adapter still works
against the real service, not a load test.
"""

from datetime import date, timedelta

import pytest

from app.market_data.providers.yfinance_provider import YFinanceProvider


@pytest.mark.integration
def test_live_get_history_for_reliance():
    provider = YFinanceProvider()
    end = date.today()
    start = end - timedelta(days=14)

    series = provider.get_history("RELIANCE.NS", "1d", start, end)

    assert series.provider_symbol == "RELIANCE.NS"
    assert len(series.bars) > 0
    last_bar = series.bars[-1]
    assert last_bar.close > 0
    assert last_bar.volume >= 0
