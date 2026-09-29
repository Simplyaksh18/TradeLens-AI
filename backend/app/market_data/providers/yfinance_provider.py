"""yfinance implementation of MarketDataProvider.

This is the ONLY module in TradeLens allowed to import yfinance directly.
All yfinance-specific exceptions and DataFrame shapes are translated at the
boundary of `get_history` into the domain types from `app.core.exceptions`
and `app.market_data.models`.

Adjustment policy (approved decision, see CLAUDE.md):
    auto_adjust=False is used deliberately, so TradeLens preserves the
    provider's raw OHLC alongside a separately reported adjusted close
    (`adj_close`). We do NOT substitute adjusted prices for raw ones. A
    corporate-action-aware unified series for backtesting is a future,
    explicitly-approved decision — not made here.
"""

from __future__ import annotations

from datetime import date as Date
from datetime import timedelta

import requests
import yfinance as yf
from yfinance.exceptions import YFException, YFRateLimitError

from app.core.exceptions import (
    EmptyProviderResponseError,
    MalformedProviderResponseError,
    ProviderUnavailableError,
    RateLimitedError,
    UnclassifiedProviderError,
)
from app.market_data.models import OHLCVSeries
from app.market_data.provider_base import MarketDataProvider
from app.market_data.providers.yfinance_normalization import normalize_yfinance_history


class YFinanceProvider(MarketDataProvider):
    """Retrieves historical daily NSE bars via yfinance."""

    def get_history(
        self,
        provider_symbol: str,
        interval: str,
        start_date: Date,
        end_date: Date,
    ) -> OHLCVSeries:
        # yfinance's `end` is exclusive; TradeLens's contract is end-inclusive.
        yfinance_end = end_date + timedelta(days=1)

        try:
            df = yf.download(
                tickers=provider_symbol,
                start=start_date.isoformat(),
                end=yfinance_end.isoformat(),
                interval=interval,
                auto_adjust=False,
                progress=False,
            )
        except YFRateLimitError as exc:
            raise RateLimitedError(
                f"yfinance reported rate limiting for {provider_symbol!r}"
            ) from exc
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout) as exc:
            raise ProviderUnavailableError(
                f"Could not reach Yahoo Finance for {provider_symbol!r}: {exc}"
            ) from exc
        except YFException as exc:
            raise UnclassifiedProviderError(
                f"yfinance raised an unrecognized error for {provider_symbol!r}: {exc}"
            ) from exc

        if df.empty:
            raise EmptyProviderResponseError(provider_symbol, start_date, end_date)

        try:
            series = normalize_yfinance_history(df, provider_symbol, interval)
        except MalformedProviderResponseError:
            raise

        return series.sliced(start_date, end_date)
