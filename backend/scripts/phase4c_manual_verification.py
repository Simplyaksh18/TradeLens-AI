"""Phase 4C manual acceptance helper (not a test -- run manually).

Builds a deterministic synthetic OHLCV/indicator fixture plus a
hand-constructed Phase 4A `SignalInvestigationDataset` (3 NEGATIVE,
3 POSITIVE, 1 BREAKEVEN, 1 UNAVAILABLE), runs it through the Phase 4C
signal-time context engine, prints per-signal context and both the
FAILED/NON_FAILED context summaries, and independently verifies expected
arithmetic and structural invariants -- it does not merely print whatever
production code happens to compute.

No network. No FastAPI/Pydantic. Run with:

    cd backend
    PYTHONPATH=. python scripts/phase4c_manual_verification.py
"""

from __future__ import annotations

import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.audit.engine import build_risk_market_context
from app.audit.models import MarketRegime
from app.indicators.models import IndicatorRow, IndicatorSeries
from app.investigation.context import build_failure_context_dataset
from app.investigation.models import SignalInvestigationClassification, SignalInvestigationDataset, SignalInvestigationObservation
from app.market_data.models import OHLCVBar, OHLCVSeries

SYMBOL = "RELIANCE.NS"
INTERVAL = "1d"
STRATEGY_ID = "trend_momentum_v1"
STRATEGY_NAME = "Trend + Momentum v1"

POSITIVE = SignalInvestigationClassification.POSITIVE
NEGATIVE = SignalInvestigationClassification.NEGATIVE
BREAKEVEN = SignalInvestigationClassification.BREAKEVEN
UNAVAILABLE = SignalInvestigationClassification.UNAVAILABLE

N_BARS = 30
DATES = [date(2024, 1, 1) + timedelta(days=i) for i in range(N_BARS)]
CLOSES = [1000.0 + i for i in range(N_BARS)]  # smooth increasing baseline, gives non-zero realized volatility

# Default valid BUY-consistent (sma20, sma50, rsi14) per index: close > sma20
# > sma50 (margins 10/20), RSI14 = 55.0 (mid-range) -- overridden below for
# the specific signals this fixture cares about.
ROWS: list[tuple[float, float, float]] = [(c - 10.0, c - 20.0, 55.0) for c in CLOSES]

# NEGATIVE (FAILED), indices 20-22: RSI 45 / 50 / 41.
ROWS[20] = (990.0, 900.0, 45.0)
ROWS[21] = (1005.0, 950.0, 50.0)
ROWS[22] = (1010.0, 990.0, 41.0)
# POSITIVE, indices 23-25: RSI 60 / 65 / 58.
ROWS[23] = (1000.0, 900.0, 60.0)
ROWS[24] = (1010.0, 950.0, 65.0)
ROWS[25] = (1015.0, 990.0, 58.0)
# BREAKEVEN, index 26: RSI 55 -- must land in NON_FAILED alongside POSITIVE.
ROWS[26] = (1010.0, 950.0, 55.0)
# UNAVAILABLE, index 27: still a valid signal-time context, but excluded
# from both summaries (its future 10-bar outcome is censored).
ROWS[27] = (1010.0, 950.0, 52.0)

NEGATIVE_INDICES = (20, 21, 22)
POSITIVE_INDICES = (23, 24, 25)
BREAKEVEN_INDEX = 26
UNAVAILABLE_INDEX = 27


def _market() -> OHLCVSeries:
    bars = tuple(
        OHLCVBar(date=d, open=c, high=c + 5, low=c - 5, close=c, adj_close=c, volume=1000) for d, c in zip(DATES, CLOSES)
    )
    return OHLCVSeries(provider_symbol=SYMBOL, interval=INTERVAL, bars=bars)


def _indicators() -> IndicatorSeries:
    rows = tuple(
        IndicatorRow(date=d, sma20=sma20, sma50=sma50, rsi14=rsi14, average_volume=None, volume_ratio=None)
        for d, (sma20, sma50, rsi14) in zip(DATES, ROWS)
    )
    return IndicatorSeries(provider_symbol=SYMBOL, interval=INTERVAL, rows=rows)


def _obs(index: int, classification: SignalInvestigationClassification) -> SignalInvestigationObservation:
    present = classification != UNAVAILABLE
    return SignalInvestigationObservation(
        signal_date=DATES[index],
        classification=classification,
        reference_close=CLOSES[index],
        forward_close_5d=CLOSES[index] * 1.01 if present else None,
        forward_return_5d=0.01 if present else None,
        forward_close_10d=CLOSES[index] * 1.02 if present else None,
        forward_return_10d=0.02 if present else None,
        mae_10d=-0.015 if present else None,
        mfe_10d=0.03 if present else None,
        available_forward_bars=15 if present else 3,
    )


def _investigation_dataset() -> SignalInvestigationDataset:
    observations = (
        tuple(_obs(i, NEGATIVE) for i in NEGATIVE_INDICES)
        + tuple(_obs(i, POSITIVE) for i in POSITIVE_INDICES)
        + (_obs(BREAKEVEN_INDEX, BREAKEVEN), _obs(UNAVAILABLE_INDEX, UNAVAILABLE))
    )
    return SignalInvestigationDataset(
        provider_symbol=SYMBOL,
        interval=INTERVAL,
        strategy_id=STRATEGY_ID,
        strategy_name=STRATEGY_NAME,
        observations=observations,
        total_signal_count=len(observations),
        eligible_count=len(NEGATIVE_INDICES) + len(POSITIVE_INDICES) + 1,
        positive_count=len(POSITIVE_INDICES),
        negative_count=len(NEGATIVE_INDICES),
        breakeven_count=1,
        unavailable_count=1,
    )


def _fmt(value: float | None) -> str:
    return "n/a" if value is None else f"{value:+.6f}"


def main() -> None:
    market = _market()
    indicators = _indicators()
    investigation_dataset = _investigation_dataset()

    result = build_failure_context_dataset(investigation_dataset, market, indicators)

    print("SOURCE POPULATION")
    print(f"  total:        {result.total_signal_count}")
    print(f"  failed:       {result.failed_count}")
    print(f"  non_failed:   {result.non_failed_count}")
    print(f"  unavailable:  {result.unavailable_count}")
    print()

    print("PER-SIGNAL CONTEXT")
    header = f"  {'Date':<12} {'Classification':<13} {'Regime':<15} {'Volatility':>11} {'RSI':>7} {'Close':>9} {'SMA20':>9} {'SMA50':>9} {'C/S20':>9} {'S20/S50':>9}"
    print(header)
    for ctx in result.observations:
        print(
            f"  {ctx.signal_date.isoformat():<12} {ctx.classification.value:<13} {ctx.regime.value:<15} "
            f"{_fmt(ctx.annualized_realized_volatility_20):>11} {ctx.rsi14:>7.2f} {ctx.close:>9.2f} {ctx.sma20:>9.2f} "
            f"{ctx.sma50:>9.2f} {ctx.close_above_sma20_fraction:>+9.4f} {ctx.sma20_above_sma50_fraction:>+9.4f}"
        )
    print()

    def print_summary(label: str, summary) -> None:
        print(label)
        print(f"  count:                              {summary.count}")
        print(f"  average RSI14:                      {_fmt(summary.average_rsi14)}")
        print(f"  median RSI14:                       {_fmt(summary.median_rsi14)}")
        print(f"  volatility available/unavailable:   {summary.volatility_available_count}/{summary.volatility_unavailable_count}")
        print(f"  average volatility:                 {_fmt(summary.average_annualized_realized_volatility_20)}")
        print(f"  median volatility:                  {_fmt(summary.median_annualized_realized_volatility_20)}")
        print(f"  average close/SMA20 fraction:       {_fmt(summary.average_close_above_sma20_fraction)}")
        print(f"  median close/SMA20 fraction:        {_fmt(summary.median_close_above_sma20_fraction)}")
        print(f"  average SMA20/SMA50 fraction:       {_fmt(summary.average_sma20_above_sma50_fraction)}")
        print(f"  median SMA20/SMA50 fraction:        {_fmt(summary.median_sma20_above_sma50_fraction)}")
        print(f"  regime counts (bull/bear/trans/insuf): {summary.bullish_trend_count}/{summary.bearish_trend_count}/{summary.transitional_count}/{summary.insufficient_data_count}")
        print()

    print_summary("FAILED CONTEXT SUMMARY", result.failed)
    print_summary("NON-FAILED CONTEXT SUMMARY", result.non_failed)

    # --- Independent verification -----------------------------------------

    # Population invariants.
    assert result.failed_count == investigation_dataset.negative_count == 3
    assert result.non_failed_count == investigation_dataset.positive_count + investigation_dataset.breakeven_count == 4
    assert result.eligible_count == result.failed_count + result.non_failed_count == 7
    assert result.total_signal_count == result.eligible_count + result.unavailable_count == 8
    assert len(result.observations) == investigation_dataset.total_signal_count
    print("Population invariants hold.")

    # BREAKEVEN in NON_FAILED, UNAVAILABLE in neither.
    non_failed_dates = {o.signal_date for o in result.observations if o.classification in (POSITIVE, BREAKEVEN)}
    failed_dates = {o.signal_date for o in result.observations if o.classification == NEGATIVE}
    assert DATES[BREAKEVEN_INDEX] in non_failed_dates
    assert DATES[UNAVAILABLE_INDEX] not in non_failed_dates
    assert DATES[UNAVAILABLE_INDEX] not in failed_dates
    print("BREAKEVEN correctly included in NON_FAILED; UNAVAILABLE correctly excluded from both.")

    # Independently hand-verified RSI mean/median.
    failed_rsi = [45.0, 50.0, 41.0]  # sorted [41, 45, 50] -> median 45
    non_failed_rsi = [60.0, 65.0, 58.0, 55.0]  # sorted [55, 58, 60, 65] -> median (58+60)/2 = 59
    assert result.failed.average_rsi14 == sum(failed_rsi) / 3
    assert result.failed.median_rsi14 == 45.0
    assert result.non_failed.average_rsi14 == sum(non_failed_rsi) / 4
    assert result.non_failed.median_rsi14 == 59.0
    print("FAILED/NON_FAILED RSI mean/median match hand-derived expected values.")

    # Every valid BUY context satisfies the structural contract.
    for ctx in result.observations:
        assert ctx.close > ctx.sma20 > ctx.sma50
        assert 40.0 <= ctx.rsi14 <= 70.0
        assert ctx.regime == MarketRegime.BULLISH_TREND
        assert ctx.close_above_sma20_fraction > 0
        assert ctx.sma20_above_sma50_fraction > 0
        # No percentage conversion: fractions stay small decimals here.
        assert abs(ctx.close_above_sma20_fraction) < 1
        assert abs(ctx.sma20_above_sma50_fraction) < 1
    print("All contexts satisfy close > SMA20 > SMA50, 40 <= RSI14 <= 70, BULLISH_TREND, and positive trend distances.")

    # Volatility cross-checked directly against the real Phase 3B function.
    for i in NEGATIVE_INDICES + POSITIVE_INDICES + (BREAKEVEN_INDEX,):
        expected_vol = build_risk_market_context(market, indicators, DATES[i]).annualized_realized_volatility_20
        actual_vol = next(o for o in result.observations if o.signal_date == DATES[i]).annualized_realized_volatility_20
        assert actual_vol == expected_vol
    print("Volatility matches the accepted Phase 3B function exactly for every signal.")

    # Deterministic rebuild.
    rebuilt = build_failure_context_dataset(investigation_dataset, market, indicators)
    assert rebuilt == result
    print("Deterministic rebuild produced an identical result.")

    print()
    print("ALL MANUAL PHASE 4C CHECKS PASSED")


if __name__ == "__main__":
    main()
