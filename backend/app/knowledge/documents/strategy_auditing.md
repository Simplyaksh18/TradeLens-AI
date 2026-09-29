# Strategy Auditing

## Purpose

The Strategy Auditor explains ONE historical decision on ONE audit date:
why the strategy evaluated the way it did, what prior signals existed,
and what risk/market context was present at that time.

## Point-in-Time Evidence

"Prior Strategy Signals" are prior BUY evaluations for the same symbol
and strategy with `signal_date < audit_date` — never described as
"similar" or "comparable market conditions" (no similarity matching
exists).

A prior signal occurring before the audit date does not automatically
mean its forward outcome was knowable on the audit date. A 5-bar or
10-bar historical outcome is only included in point-in-time statistics
when that horizon's forward bar index is on or before the audit index —
pure trading-bar index arithmetic, never calendar-day math.

## No Future Evidence Leakage

Every point-in-time section (the evaluation itself, prior-signal
statistics, and risk/market context) is provably unaffected by any bar
strictly after the audit date. Only one section — the retrospective
outcome — is explicit, clearly separated hindsight: it is what actually
happened after the audit date, shown for reference, and it never
influences any point-in-time section.

## Calculation History vs. Evidence Window

The data fetched to calculate indicators (warm-up) is a separate concern
from which historical signals are counted as evidence. Narrowing the
requested evidence window must never starve indicator warm-up and
fabricate an incorrect decision.
