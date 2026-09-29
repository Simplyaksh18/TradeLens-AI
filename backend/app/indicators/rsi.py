"""Wilder RSI (Relative Strength Index).

Uses raw `close` (never `adj_close` — see CLAUDE.md Phase 1B/1C notes on
preserving raw vs adjusted prices; no approved decision currently overrides
this default).

Wilder's method, period N (14 here):
  1. price changes: delta[i] = close[i] - close[i-1]
  2. gain[i] = max(delta[i], 0), loss[i] = max(-delta[i], 0)
  3. seed average (index N, 0-based bar index): simple arithmetic mean of
     the first N gains/losses (deltas 1..N) — NOT an exponential average
     from a single starting value.
  4. every subsequent average: Wilder smoothing,
     avg[i] = (avg[i-1] * (N-1) + value[i]) / N
     (equivalent to an EMA with alpha = 1/N, but seeded as in step 3 — this
     is deliberately NOT `pandas.ewm(alpha=1/N, adjust=False)`, which seeds
     from the first single observation instead of a simple N-period average
     and would silently produce a different, non-Wilder value).
  5. RSI = 100 - 100 / (1 + avg_gain/avg_loss), with explicit conventions
     for the zero-denominator edge cases (see `_rsi_from_averages`) — no
     accidental NaN/inf from an unguarded division.

First valid RSI is at bar index N (0-based) — the (N+1)-th observation is
required to have N price changes. Bars before that are warm-up: `None`.

No look-ahead: each avg/RSI value only ever incorporates deltas up to and
including its own bar index.
"""

from __future__ import annotations

from typing import Optional, Sequence


def rsi_wilder(closes: Sequence[float], period: int = 14) -> list[Optional[float]]:
    if period < 1:
        raise ValueError(f"period must be >= 1, got {period}")

    closes = list(closes)
    n = len(closes)
    result: list[Optional[float]] = [None] * n

    if n < period + 1:
        return result

    deltas = [closes[i] - closes[i - 1] for i in range(1, n)]
    gains = [max(d, 0.0) for d in deltas]
    losses = [max(-d, 0.0) for d in deltas]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    result[period] = _rsi_from_averages(avg_gain, avg_loss)

    for i in range(period, len(deltas)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        result[i + 1] = _rsi_from_averages(avg_gain, avg_loss)

    return result


def _rsi_from_averages(avg_gain: float, avg_loss: float) -> float:
    """Explicit flat-market/zero-denominator convention (approved for Phase 1C):

      - avg_gain == 0 and avg_loss == 0 (no price movement at all over the
        period): RSI = 50 — neutral, since there is no directional evidence
        either way. This avoids an undefined 0/0 division.
      - avg_loss == 0, avg_gain > 0 (all gains): RSI = 100.
      - avg_gain == 0, avg_loss > 0 (all losses): RSI = 0.
      - otherwise: the standard RS = avg_gain / avg_loss formula.
    """
    if avg_gain == 0.0 and avg_loss == 0.0:
        return 50.0
    if avg_loss == 0.0:
        return 100.0
    if avg_gain == 0.0:
        return 0.0
    rs = avg_gain / avg_loss
    return 100.0 - (100.0 / (1.0 + rs))
