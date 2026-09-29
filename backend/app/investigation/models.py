"""Phase 4A domain model: deterministic historical BUY-signal investigation
dataset, derived from accepted Phase 2A `SignalOutcome`/`SignalOutcomeSeries`
results (see app.outcomes).

Phase 4 is retrospective historical research: "for each historical BUY
signal, what observable 10-trading-bar outcome classification does it
belong to?" Phase 4A performs classification ONLY -- it does not explain
why a signal succeeded or failed, does not identify a cause, and does not
compare populations (those are later Phase 4 subphases; see CLAUDE.md
Phase 4 decomposition). "Failed signal" under this explicit Phase 4 v1
research definition means only "an eligible observation whose accepted
10-trading-bar forward return is strictly negative" -- never a claim that
the strategy is globally defective, and never a causal explanation.

Primary investigation horizon (Phase 4 v1, frozen): 10 TRADING BARS. A
signal is classified POSITIVE/NEGATIVE/BREAKEVEN only when its full 10-bar
outcome (forward_close_10d, forward_return_10d, mae_10d, mfe_10d -- the
exact fields Phase 2A's accepted contract populates together as a group)
is available; otherwise it is UNAVAILABLE, regardless of whether a 5-bar
outcome exists. UNAVAILABLE/censored observations are never interpreted as
failure or success -- incomplete future history must never be silently
read as poor strategy performance.

This package reuses Phase 2A values verbatim -- it never recalculates a
forward close/return, MAE, or MFE (see engine.py for the classification
rule and its explicit no-look-ahead-into-the-original-decision guarantee).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as Date
from enum import Enum


class SignalInvestigationClassification(str, Enum):
    """Phase 4 v1 primary classification of one BUY signal's 10-trading-bar
    forward outcome. Exact/strict, no epsilon, no threshold (see
    engine.py): POSITIVE means `forward_return_10d > 0`, NEGATIVE means
    `forward_return_10d < 0`, BREAKEVEN means `forward_return_10d == 0`.
    UNAVAILABLE means the full 10-bar outcome is not yet observable
    (censored) -- it is NOT a failure classification and must never be
    counted toward `negative_count`/`positive_count`/`breakeven_count`."""

    POSITIVE = "POSITIVE"
    NEGATIVE = "NEGATIVE"
    BREAKEVEN = "BREAKEVEN"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class SignalInvestigationObservation:
    """One historical BUY signal's Phase 4 investigation record.

    All outcome fields below are Phase 2A `SignalOutcome` values, reused
    verbatim -- never rounded, never multiplied by 100 (no percentage
    conversion), never abs()'d (signed MAE/MFE preserved exactly).
    `classification` is derived ONLY from `forward_return_10d` per the
    Phase 4 v1 rule in engine.py; it describes WHAT the 10-bar outcome was,
    never WHY it occurred."""

    signal_date: Date
    classification: SignalInvestigationClassification
    reference_close: float
    forward_close_5d: float | None
    forward_return_5d: float | None
    forward_close_10d: float | None
    forward_return_10d: float | None
    mae_10d: float | None
    mfe_10d: float | None
    available_forward_bars: int


@dataclass(frozen=True)
class SignalInvestigationDataset:
    """The complete Phase 4A investigation population for one
    symbol/strategy.

    `observations` preserves the exact order of the upstream
    `SignalOutcomeSeries` (chronological by signal date -- see engine.py)
    -- Phase 4A never reorders by return/MAE/MFE/classification/severity;
    later Phase 4 subphases may rank/filter explicitly.

    Invariants (enforced by construction in engine.py, not merely
    documented):
        total_signal_count == len(observations)
        eligible_count == positive_count + negative_count + breakeven_count
        total_signal_count == eligible_count + unavailable_count

    Every accepted Phase 2A BUY outcome appears exactly once -- censored
    observations are retained in `observations` and counted in
    `unavailable_count`, never silently discarded.
    """

    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str
    observations: tuple[SignalInvestigationObservation, ...]
    total_signal_count: int
    eligible_count: int
    positive_count: int
    negative_count: int
    breakeven_count: int
    unavailable_count: int
