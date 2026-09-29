# Research Limitations

## Hindsight vs. Point-in-Time

Retrospective outcomes (what happened after a signal) are hindsight —
information that was not available to the strategy at decision time.
Signal-time context (regime, RSI, volatility, SMA relationships) is
strictly point-in-time. TradeLens always keeps these two categories of
information visually and structurally distinct so hindsight is never
mistaken for evidence that was available when a decision was made.

## Association, Not Causation

Historical association between a signal-time condition and a later
outcome does not establish that the condition caused the outcome. No
TradeLens research output computes statistical significance, feature
importance, or a confidence score.

## Past Performance Does Not Predict Future Results

Backtested and historical results describe what happened in a specific
historical period under specific, explicitly documented assumptions
(raw prices, no slippage/cost model in v1, next-bar-open execution).
They are not a guarantee, projection, or promise of future performance.

## Provider Data Reproducibility

Historical market data can be revised, backfilled, or corrected by the
upstream data provider between requests. Re-running an identical
historical query at a later date is not guaranteed to return byte-
identical results. This is a property of the external data provider, not
a TradeLens calculation defect — TradeLens's own deterministic
calculations produce the same output for the same input every time.

## No Personalized Advice

TradeLens is a research and educational system. It does not provide
personalized investment advice, and it does not guarantee signal
accuracy or future returns.
