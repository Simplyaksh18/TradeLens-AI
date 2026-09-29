"""
Isolated yfinance feasibility test for TradeLens AI.

Purpose: determine whether this environment can reliably retrieve NSE
historical data via yfinance, BEFORE any TradeLens architecture is built.

Deliberately makes the minimum number of network requests:
  1. Single symbol, default (auto_adjust=True)
  2. Same symbol, same period, auto_adjust=False   (adjustment comparison)
  3. Five-symbol bulk request
  4. One intentionally invalid symbol

No retries. No loops. No concurrency. Not an integration test / not wired
into the TradeLens app.
"""

import time
import traceback

import yfinance as yf

SEPARATOR = "=" * 70


def describe_dataframe(df, label):
    print(f"--- {label} ---")
    print(f"shape: {df.shape}")
    print(f"columns: {list(df.columns)}")
    print(f"columns dtype/type: {type(df.columns)}")
    if df.empty:
        print("DataFrame is EMPTY")
        return
    print(f"index dtype: {df.index.dtype}, tz: {getattr(df.index, 'tz', None)}")
    print(f"first row:\n{df.iloc[[0]]}")
    print(f"last row:\n{df.iloc[[-1]]}")


def single_symbol_test():
    print(SEPARATOR)
    print("TEST 1: Single symbol, default auto_adjust (True), ~1 year daily")
    print(SEPARATOR)
    symbol = "RELIANCE.NS"
    try:
        start = time.monotonic()
        df = yf.download(symbol, period="1y", interval="1d", progress=False)
        duration = time.monotonic() - start
        print(f"status: SUCCESS")
        print(f"duration: {duration:.2f}s")
        describe_dataframe(df, f"{symbol} auto_adjust=True (default)")
        return df
    except Exception as e:
        print("status: EXCEPTION")
        print(f"exception type: {type(e).__name__}")
        print(f"exception message: {e}")
        traceback.print_exc()
        return None


def adjustment_test():
    print(SEPARATOR)
    print("TEST 2: Same symbol/period, auto_adjust=False (adjustment comparison)")
    print(SEPARATOR)
    symbol = "RELIANCE.NS"
    try:
        start = time.monotonic()
        df = yf.download(symbol, period="1y", interval="1d", progress=False, auto_adjust=False)
        duration = time.monotonic() - start
        print(f"status: SUCCESS")
        print(f"duration: {duration:.2f}s")
        describe_dataframe(df, f"{symbol} auto_adjust=False")
        return df
    except Exception as e:
        print("status: EXCEPTION")
        print(f"exception type: {type(e).__name__}")
        print(f"exception message: {e}")
        traceback.print_exc()
        return None


def five_symbol_test():
    print(SEPARATOR)
    print("TEST 3: Five-symbol bulk request")
    print(SEPARATOR)
    symbols = ["RELIANCE.NS", "INFY.NS", "TCS.NS", "HDFCBANK.NS", "ICICIBANK.NS"]
    try:
        start = time.monotonic()
        df = yf.download(symbols, period="6mo", interval="1d", progress=False, group_by="ticker")
        duration = time.monotonic() - start
        print(f"status: SUCCESS (call completed without exception)")
        print(f"duration: {duration:.2f}s")
        print(f"shape: {df.shape}")
        print(f"columns type: {type(df.columns)}")
        print(f"top-level columns: {list(df.columns.get_level_values(0).unique())}")
        for sym in symbols:
            try:
                sub = df[sym]
                non_null_rows = sub.dropna(how="all").shape[0]
                print(f"  {sym}: rows={sub.shape[0]}, non-empty rows={non_null_rows}, "
                      f"columns={list(sub.columns)}")
            except KeyError:
                print(f"  {sym}: MISSING from result")
        return df
    except Exception as e:
        print("status: EXCEPTION")
        print(f"exception type: {type(e).__name__}")
        print(f"exception message: {e}")
        traceback.print_exc()
        return None


def invalid_symbol_test():
    print(SEPARATOR)
    print("TEST 4: Intentionally invalid NSE-style symbol")
    print(SEPARATOR)
    symbol = "THISISNOTAREALSYMBOL.NS"
    try:
        start = time.monotonic()
        df = yf.download(symbol, period="6mo", interval="1d", progress=False)
        duration = time.monotonic() - start
        print(f"status: call completed without exception")
        print(f"duration: {duration:.2f}s")
        describe_dataframe(df, f"{symbol}")
    except Exception as e:
        print("status: EXCEPTION")
        print(f"exception type: {type(e).__name__}")
        print(f"exception message: {e}")
        traceback.print_exc()


if __name__ == "__main__":
    print(f"yfinance version: {yf.__version__}")
    single_symbol_test()
    adjustment_test()
    five_symbol_test()
    invalid_symbol_test()
    print(SEPARATOR)
    print("Feasibility test complete. No further requests will be made.")
