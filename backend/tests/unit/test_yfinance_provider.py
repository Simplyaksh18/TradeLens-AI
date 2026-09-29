from datetime import date

import pandas as pd
import pytest
import requests
from yfinance.exceptions import YFRateLimitError

from app.core.exceptions import (
    EmptyProviderResponseError,
    ProviderUnavailableError,
    RateLimitedError,
)
from app.market_data.providers.yfinance_provider import YFinanceProvider


def _multiindex_df(symbol="RELIANCE.NS"):
    dates = pd.to_datetime(["2026-01-02"])
    columns = pd.MultiIndex.from_product(
        [["Adj Close", "Close", "High", "Low", "Open", "Volume"], [symbol]]
    )
    return pd.DataFrame(
        [[104.0, 104.0, 105.0, 99.0, 100.0, 1000]], index=dates, columns=columns
    )


def test_get_history_returns_normalized_series_on_success(mocker):
    mocker.patch(
        "app.market_data.providers.yfinance_provider.yf.download",
        return_value=_multiindex_df(),
    )
    provider = YFinanceProvider()

    series = provider.get_history("RELIANCE.NS", "1d", date(2026, 1, 1), date(2026, 1, 3))

    assert series.provider_symbol == "RELIANCE.NS"
    assert len(series.bars) == 1
    assert series.bars[0].close == 104.0


def test_empty_response_raises_empty_provider_response_error(mocker):
    mocker.patch(
        "app.market_data.providers.yfinance_provider.yf.download",
        return_value=pd.DataFrame(),
    )
    provider = YFinanceProvider()

    with pytest.raises(EmptyProviderResponseError):
        provider.get_history("INVALID.NS", "1d", date(2026, 1, 1), date(2026, 1, 3))


def test_rate_limit_exception_is_reclassified(mocker):
    mocker.patch(
        "app.market_data.providers.yfinance_provider.yf.download",
        side_effect=YFRateLimitError(),
    )
    provider = YFinanceProvider()

    with pytest.raises(RateLimitedError):
        provider.get_history("RELIANCE.NS", "1d", date(2026, 1, 1), date(2026, 1, 3))


def test_connection_error_is_reclassified_as_provider_unavailable(mocker):
    mocker.patch(
        "app.market_data.providers.yfinance_provider.yf.download",
        side_effect=requests.exceptions.ConnectionError("network down"),
    )
    provider = YFinanceProvider()

    with pytest.raises(ProviderUnavailableError):
        provider.get_history("RELIANCE.NS", "1d", date(2026, 1, 1), date(2026, 1, 3))
