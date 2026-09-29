# Deterministic Backtesting Methodology

## Timing

A BUY or NO_SIGNAL evaluation observed at bar T (based on T's Close) can
only affect execution at bar T+1's OPEN — never T's own OPEN. A signal
observed on the final bar of available data with no T+1 OPEN never
fabricates a fill; it stays pending.

## State Machine

- FLAT + BUY schedules an entry for the next bar.
- LONG + BUY is a no-op (stay long; no pyramiding or averaging in).
- The first NO_SIGNAL observed while LONG schedules an exit for the next
  bar.
- FLAT + NO_SIGNAL is a no-op.
- INSUFFICIENT_DATA never triggers any action, regardless of state.

## Position and Pricing

Long only, at most one open position, no leverage, no shorting, no
fractional shares. `quantity = floor(cash / entry_price)`; a quantity of
zero or less means no executable position (stays FLAT, not an error).
Cash can never go negative by construction. `entry_price`/`exit_price`
are always the raw OPEN; equity mark-to-market uses the raw CLOSE —
never `adj_close`, and never Phase 2A's `reference_close`.

## Costs

Transaction cost and slippage are explicit configuration fields, but the
v1 execution model defines no cost model: any nonzero value is rejected
explicitly rather than silently ignored. Under the v1 zero-cost baseline,
net P&L equals gross P&L.

## No Look-Ahead

Execution decisions read only the current/past evaluation and the very
next bar's OPEN — never forward-return, MAE/MFE, or any future-outcome
field from the signal-outcome research primitive.
