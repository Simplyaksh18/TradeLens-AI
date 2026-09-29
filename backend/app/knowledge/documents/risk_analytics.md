# Performance & Risk Analytics

## Two Populations

Trade statistics (win rate, average/median/best/worst trade return,
winner/loser/breakeven counts) use CLOSED trades only — an open position
is never counted as a winner, loser, breakeven, or closed trade.
Portfolio/equity statistics (total return, drawdown, exposure) use the
complete equity curve, so an open position's mark-to-market value is
reflected through unrealized P&L and ending equity.

## Core Definitions

- `total_return = ending_equity / initial_equity - 1`.
- Winner/loser/breakeven use strict `net_pnl > 0` / `< 0` / `== 0` — no
  epsilon.
- `win_rate` is `None` (never `0.0`) when there are zero closed trades —
  "no observations" is not "0% winners".
- Drawdown at each equity point is `equity_t / running_peak_t - 1`,
  always `<= 0`. The running peak's date only updates on a strictly
  greater equity value.
- Exposure is bar-based: the fraction of equity points where a position
  was held, not elapsed clock time.

## Deferred Metrics

Annualized volatility, CAGR, Sharpe/Sortino/Calmar ratios, alpha/beta,
benchmark comparison, VaR/CVaR, and rolling analytics are explicitly
deferred — they are not part of the accepted v1 analytics contract and
must not be assumed present.
