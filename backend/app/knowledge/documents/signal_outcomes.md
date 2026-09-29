# Historical Signal Outcomes

## Purpose

Signal outcomes answer "what happened to price after a historical BUY
signal" — a pure research primitive, not a portfolio backtester and not
an execution assumption.

## Horizons

Outcomes use two fixed TRADING-BAR horizons, never calendar-day offsets:

- `+5` trading bars (`bars[i+5]`)
- `+10` trading bars (`bars[i+10]`)

`reference_close` is the raw `close` at the signal bar — the same value
the strategy evaluated — never `adj_close`, and deliberately not called
an entry/fill price (no execution assumption exists at this layer).

## MAE / MFE

Maximum Adverse Excursion (MAE) and Maximum Favorable Excursion (MFE) use
a full 10-trading-bar window strictly AFTER the signal bar
(`bars[i+1:i+11]`, the signal bar itself excluded) — future LOW for MAE,
future HIGH for MFE, never Close. Sign is whatever the data implies: MAE
can be positive if the whole future window traded above the reference
close, and MFE can be small or near-zero. Neither is assumed
negative/positive by convention, and neither is ever `abs()`'d.

## Full-Window Requirement and Censoring

A 10-bar outcome (`forward_close_10d`, `forward_return_10d`, `mae_10d`,
`mfe_10d`) is only ever populated as a complete set — all four together,
or all four `None`. A partial window near the end of available data is
never presented as a full 10-bar measurement. `available_forward_bars`
is always reported, uncapped, so callers can see exactly how much
forward history existed. Every historical BUY signal produces an outcome
record — end-of-series signals are preserved with explicit `None`
fields, never dropped, invented, or silently shortened.

## Independence

Consecutive BUY evaluations are NOT collapsed into one outcome — each
qualifying historical BUY stays an independent observation.
