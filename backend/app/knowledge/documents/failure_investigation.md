# Strategy Failure Investigation

## Purpose

Failure investigation compares FAILED and NON-FAILED historical BUY
signals — descriptive, retrospective research over a population of
signals, never a claim about causation, prediction, statistical
significance, or a trading recommendation.

## Classification

Each eligible historical BUY signal is classified from its accepted
10-trading-bar forward return:

- `NEGATIVE` (FAILED) — forward return strictly negative.
- `POSITIVE` — forward return strictly positive.
- `BREAKEVEN` — forward return exactly zero.
- `UNAVAILABLE` — the 10-bar outcome is not yet observable (fewer than
  10 forward trading bars exist in the research window).

## Population Definitions

FAILED = NEGATIVE. NON-FAILED = POSITIVE or BREAKEVEN (never called
"successful", since BREAKEVEN is included). UNAVAILABLE participates in
NEITHER population — it is excluded from both comparison populations,
but it is still counted in the total signal count and retained in the
full observation list, never silently dropped.

## Two Kinds of Comparison

Retrospective outcome comparison (10-bar forward return, MAE, MFE) is
observed AFTER each signal. Signal-time context comparison (RSI14,
20-bar realized volatility, market regime, trend-distance fractions) is
the market/strategy condition present WHEN each signal fired — computed
strictly from information available at or before the signal date. These
two kinds of evidence are kept structurally separate and are never
merged into one generic "features" object.

## Descriptive, Not Causal

An observed difference between FAILED and NON-FAILED populations is an
association, not a cause. Failure investigation never claims a factor
predicts failure, never computes statistical significance, and never
issues a trading recommendation.
