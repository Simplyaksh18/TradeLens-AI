# Trend + Momentum v1 Strategy

## BUY Rule

Trend + Momentum v1 evaluates one BUY rule per bar. All conditions must
hold simultaneously:

- `close > SMA20` (strict, no epsilon)
- `SMA20 > SMA50` (strict, no epsilon)
- `40 <= RSI14 <= 70` (inclusive on both bounds, no epsilon)

Strategy uses raw `close`, never `adj_close`.

## Decisions

The strategy produces exactly one of three decisions per bar:

- `BUY` — all three conditions hold.
- `NO_SIGNAL` — all required inputs are present but at least one
  condition fails.
- `INSUFFICIENT_DATA` — any single required input (`close`, `sma20`,
  `sma50`, `rsi14`) is missing (indicator warm-up). When this happens,
  zero conditions are evaluated — there is no partial evidence.

There is no `HOLD` or `SELL` decision in v1. SELL semantics have not been
approved for TradeLens.

## Independence of Evaluations

Every bar is evaluated independently. A run of several consecutive BUY
days is not a single "entry event" — it is several independent BUY
decisions. Collapsing consecutive BUY days into a single position/entry
is a backtesting-layer concern (see backtesting_methodology.md), not a
strategy-evaluation concern.

## Explainability

Each evaluation carries structured per-condition evidence (actual value,
reference/threshold, pass/fail) so a decision is never a black box.
