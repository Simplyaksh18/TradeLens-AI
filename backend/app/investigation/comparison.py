"""Phase 4B: deterministic failure / non-failure population comparison
engine.

Consumes an already-accepted Phase 4A `SignalInvestigationDataset`
(app.investigation.engine/models) and produces purely DESCRIPTIVE summary
statistics for two disjoint comparison populations:

    FAILED       = observations classified NEGATIVE
    NON_FAILED   = observations classified POSITIVE or BREAKEVEN

UNAVAILABLE (censored) observations participate in NEITHER population --
incomplete future history must never be silently read as poor strategy
performance (see CLAUDE.md Phase 4A). Phase 4A's classification is
authoritative and is never recomputed, reinterpreted, or re-thresholded
here.

This module performs classification-based DESCRIPTION only. It does not
claim causation, prediction, confidence, or statistical significance, and
it must never be extended with language implying any of those (e.g. "high
MAE causes failure"). Those would require carefully-defined association
analysis reserved for a later Phase 4 sub-phase.

Zero coupling to Phase 2B backtesting, Phase 2C analytics, Phase 3 audit,
FastAPI, Pydantic, or any AI/LLM/RAG component -- pure Python/stdlib
domain logic only (see CLAUDE.md Phase 4B).
"""

from __future__ import annotations

import statistics
from dataclasses import dataclass
from math import isfinite

from app.core.exceptions import InvestigationInputInvalidError
from app.investigation.models import (
    SignalInvestigationClassification,
    SignalInvestigationDataset,
    SignalInvestigationObservation,
)

_NON_FAILED_CLASSIFICATIONS = (
    SignalInvestigationClassification.POSITIVE,
    SignalInvestigationClassification.BREAKEVEN,
)


@dataclass(frozen=True)
class PopulationSummary:
    """Deterministic descriptive summary of one Phase 4B comparison
    population (FAILED or NON_FAILED).

    Every numeric field is the exact accepted Phase 2A decimal fraction
    (via Phase 4A's preserved observation fields) -- never rounded, never
    abs()'d (signed `mae`/`mfe` preserved exactly), never multiplied by
    100, never winsorized/trimmed/annualized/normalized. `worst_mae_10d`
    is the minimum (most negative) signed MAE; `best_mfe_10d` is the
    maximum signed MFE. When `count == 0`, every numeric field is `None`
    -- never a fabricated `0.0`."""

    count: int
    average_forward_return_10d: float | None
    median_forward_return_10d: float | None
    average_mae_10d: float | None
    median_mae_10d: float | None
    worst_mae_10d: float | None
    average_mfe_10d: float | None
    median_mfe_10d: float | None
    best_mfe_10d: float | None


_EMPTY_SUMMARY = PopulationSummary(
    count=0,
    average_forward_return_10d=None,
    median_forward_return_10d=None,
    average_mae_10d=None,
    median_mae_10d=None,
    worst_mae_10d=None,
    average_mfe_10d=None,
    median_mfe_10d=None,
    best_mfe_10d=None,
)


@dataclass(frozen=True)
class FailurePopulationComparison:
    """Phase 4B result: descriptive FAILED vs. NON_FAILED comparison over
    one Phase 4A `SignalInvestigationDataset`.

    `total_signal_count`/`unavailable_count` are carried through from the
    source dataset unchanged; `eligible_count` is recomputed here as
    `failed.count + non_failed.count` and is asserted (by construction) to
    equal the source dataset's own `eligible_count`. This is a
    descriptive comparison only -- see the module docstring for what this
    result must never claim."""

    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str
    total_signal_count: int
    eligible_count: int
    unavailable_count: int
    failed: PopulationSummary
    non_failed: PopulationSummary


def build_failure_population_comparison(dataset: SignalInvestigationDataset) -> FailurePopulationComparison:
    """Build the Phase 4B FAILED vs. NON_FAILED descriptive comparison from
    an accepted Phase 4A `SignalInvestigationDataset`.

    Does not mutate `dataset` or reorder its `observations`. Raises
    InvestigationInputInvalidError if the dataset's own declared population
    counts are inconsistent with its `observations`, or if an eligible
    (POSITIVE/NEGATIVE/BREAKEVEN) observation is missing, or has a
    non-finite, `forward_return_10d`/`mae_10d`/`mfe_10d` -- Phase 4A
    guarantees this for output it produces itself, but Phase 4B defends its
    own comparison-metric assumptions independently rather than trusting a
    dataset it did not itself validate end-to-end.
    """
    failed_observations = tuple(
        o for o in dataset.observations if o.classification == SignalInvestigationClassification.NEGATIVE
    )
    non_failed_observations = tuple(
        o for o in dataset.observations if o.classification in _NON_FAILED_CLASSIFICATIONS
    )

    failed_count = len(failed_observations)
    non_failed_count = len(non_failed_observations)

    if failed_count != dataset.negative_count:
        raise InvestigationInputInvalidError(
            f"Phase 4A dataset declares negative_count={dataset.negative_count}, but "
            f"{failed_count} observation(s) are actually classified NEGATIVE."
        )
    if non_failed_count != dataset.positive_count + dataset.breakeven_count:
        raise InvestigationInputInvalidError(
            f"Phase 4A dataset declares positive_count={dataset.positive_count} + "
            f"breakeven_count={dataset.breakeven_count} = {dataset.positive_count + dataset.breakeven_count}, but "
            f"{non_failed_count} observation(s) are actually classified POSITIVE or BREAKEVEN."
        )

    eligible_count = failed_count + non_failed_count
    if dataset.total_signal_count != eligible_count + dataset.unavailable_count:
        raise InvestigationInputInvalidError(
            f"Phase 4A dataset declares total_signal_count={dataset.total_signal_count}, but "
            f"eligible_count ({eligible_count}) + unavailable_count ({dataset.unavailable_count}) = "
            f"{eligible_count + dataset.unavailable_count}."
        )

    return FailurePopulationComparison(
        provider_symbol=dataset.provider_symbol,
        interval=dataset.interval,
        strategy_id=dataset.strategy_id,
        strategy_name=dataset.strategy_name,
        total_signal_count=dataset.total_signal_count,
        eligible_count=eligible_count,
        unavailable_count=dataset.unavailable_count,
        failed=_summarize(failed_observations),
        non_failed=_summarize(non_failed_observations),
    )


def _summarize(observations: tuple[SignalInvestigationObservation, ...]) -> PopulationSummary:
    if not observations:
        return _EMPTY_SUMMARY

    returns = [_required_finite_field(o, "forward_return_10d", o.forward_return_10d) for o in observations]
    maes = [_required_finite_field(o, "mae_10d", o.mae_10d) for o in observations]
    mfes = [_required_finite_field(o, "mfe_10d", o.mfe_10d) for o in observations]

    return PopulationSummary(
        count=len(observations),
        average_forward_return_10d=sum(returns) / len(returns),
        median_forward_return_10d=statistics.median(returns),
        average_mae_10d=sum(maes) / len(maes),
        median_mae_10d=statistics.median(maes),
        worst_mae_10d=min(maes),
        average_mfe_10d=sum(mfes) / len(mfes),
        median_mfe_10d=statistics.median(mfes),
        best_mfe_10d=max(mfes),
    )


def _required_finite_field(observation: SignalInvestigationObservation, field_name: str, value: float | None) -> float:
    if value is None:
        raise InvestigationInputInvalidError(
            f"Eligible signal observation at {observation.signal_date} "
            f"(classification={observation.classification.value}) is missing required field {field_name!r} -- "
            "an eligible (POSITIVE/NEGATIVE/BREAKEVEN) observation must have a complete 10-bar outcome."
        )
    if not isfinite(value):
        raise InvestigationInputInvalidError(
            f"Eligible signal observation at {observation.signal_date} "
            f"(classification={observation.classification.value}) has a non-finite {field_name!r} value ({value!r})."
        )
    return value
