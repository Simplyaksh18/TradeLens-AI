"""Phase 4A: deterministic historical BUY-signal investigation dataset
engine.

Converts an already-accepted Phase 2A `SignalOutcomeSeries` into a
`SignalInvestigationDataset` by classifying each outcome's 10-trading-bar
forward return. This is the ONLY thing Phase 4A does -- it does not
determine why a signal failed, does not compare populations, and does not
identify associations (see CLAUDE.md Phase 4 for the full decomposition).

Retrospective research, not look-ahead into the original decision:
`forward_return_10d`/`mae_10d`/`mfe_10d` ARE future information relative to
each signal's own date -- that is expected and intentional here, because
Phase 4 explicitly investigates what happened after a historical signal.
This module never feeds these values back into, or otherwise mutates, the
Phase 1D strategy decision or the Phase 2A outcome it reads -- it only
reads already-computed values and classifies them. It does not couple to
Phase 2B backtesting, Phase 2C analytics, Phase 3 audit, FastAPI, or any
AI/LLM component.
"""

from __future__ import annotations

from math import isfinite

from app.core.exceptions import InvestigationInputInvalidError
from app.investigation.models import (
    SignalInvestigationClassification,
    SignalInvestigationDataset,
    SignalInvestigationObservation,
)
from app.outcomes.models import SignalOutcome, SignalOutcomeSeries
from app.strategies.models import StrategyDecision


def build_signal_investigation_dataset(outcome_series: SignalOutcomeSeries) -> SignalInvestigationDataset:
    """Build the Phase 4A investigation dataset from an accepted Phase 2A
    `SignalOutcomeSeries`.

    Every outcome in `outcome_series.outcomes` appears exactly once in the
    result, in the same order Phase 2A already produced them (chronological
    by signal date -- `compute_signal_outcomes` iterates the aligned series
    in order, so no additional sort is performed or required here).

    Raises InvestigationInputInvalidError if an outcome's `decision` is not
    BUY, if an outcome's 10-bar fields are only partially present (Phase
    2A's own contract populates `forward_close_10d`/`forward_return_10d`/
    `mae_10d`/`mfe_10d` together or not at all), or if a present
    `forward_return_10d` is non-finite.
    """
    observations = tuple(_classify(outcome) for outcome in outcome_series.outcomes)

    positive_count = _count(observations, SignalInvestigationClassification.POSITIVE)
    negative_count = _count(observations, SignalInvestigationClassification.NEGATIVE)
    breakeven_count = _count(observations, SignalInvestigationClassification.BREAKEVEN)
    unavailable_count = _count(observations, SignalInvestigationClassification.UNAVAILABLE)
    eligible_count = positive_count + negative_count + breakeven_count

    return SignalInvestigationDataset(
        provider_symbol=outcome_series.provider_symbol,
        interval=outcome_series.interval,
        strategy_id=outcome_series.strategy_id,
        strategy_name=outcome_series.strategy_name,
        observations=observations,
        total_signal_count=len(observations),
        eligible_count=eligible_count,
        positive_count=positive_count,
        negative_count=negative_count,
        breakeven_count=breakeven_count,
        unavailable_count=unavailable_count,
    )


def _count(observations: tuple[SignalInvestigationObservation, ...], classification: SignalInvestigationClassification) -> int:
    return sum(1 for o in observations if o.classification == classification)


def _classify(outcome: SignalOutcome) -> SignalInvestigationObservation:
    if outcome.decision != StrategyDecision.BUY:
        raise InvestigationInputInvalidError(
            f"Signal outcome at {outcome.date} has decision={outcome.decision.value}, not BUY -- "
            "Phase 2A's contract guarantees a SignalOutcome only exists for a BUY evaluation."
        )

    ten_bar_fields = (outcome.forward_close_10d, outcome.forward_return_10d, outcome.mae_10d, outcome.mfe_10d)
    ten_bar_present = [field is not None for field in ten_bar_fields]

    if all(ten_bar_present):
        forward_return_10d = outcome.forward_return_10d
        assert forward_return_10d is not None  # narrowed by `all(ten_bar_present)` above
        if not isfinite(forward_return_10d):
            raise InvestigationInputInvalidError(
                f"Signal outcome at {outcome.date} has a non-finite forward_return_10d "
                f"({forward_return_10d!r}) despite presenting a full 10-bar horizon."
            )
        classification = _classify_return(forward_return_10d)
    elif not any(ten_bar_present):
        classification = SignalInvestigationClassification.UNAVAILABLE
    else:
        raise InvestigationInputInvalidError(
            f"Signal outcome at {outcome.date} has a structurally inconsistent 10-bar horizon "
            f"(forward_close_10d={outcome.forward_close_10d!r}, forward_return_10d={outcome.forward_return_10d!r}, "
            f"mae_10d={outcome.mae_10d!r}, mfe_10d={outcome.mfe_10d!r}) -- Phase 2A's contract populates all "
            "four fields together (a full window) or none at all (censored); a partial set indicates "
            "malformed/inconsistent upstream data."
        )

    return SignalInvestigationObservation(
        signal_date=outcome.date,
        classification=classification,
        reference_close=outcome.reference_close,
        forward_close_5d=outcome.forward_close_5d,
        forward_return_5d=outcome.forward_return_5d,
        forward_close_10d=outcome.forward_close_10d,
        forward_return_10d=outcome.forward_return_10d,
        mae_10d=outcome.mae_10d,
        mfe_10d=outcome.mfe_10d,
        available_forward_bars=outcome.available_forward_bars,
    )


def _classify_return(forward_return_10d: float) -> SignalInvestigationClassification:
    """Exact/strict classification -- no epsilon, no rounding, no
    percentage conversion, no configurable failure threshold (Phase 4 v1)."""
    if forward_return_10d > 0:
        return SignalInvestigationClassification.POSITIVE
    if forward_return_10d < 0:
        return SignalInvestigationClassification.NEGATIVE
    return SignalInvestigationClassification.BREAKEVEN
