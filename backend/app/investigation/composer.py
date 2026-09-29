"""Phase 4D: deterministic Strategy Failure Investigation composer.

This module is intentionally boring: it VALIDATES and ASSEMBLES the
already-accepted Phase 4A/4B/4C research outputs into one coherent
`StrategyFailureInvestigation` result. It does not calculate a single
forward return, MAE, MFE, mean, median, RSI, SMA, volatility, regime, or
trend distance -- every one of those values already exists in an accepted
upstream result and is carried through unchanged (embedded by reference,
via `outcome_comparison`/`context_analysis`, never copied field-by-field
into a new shape).

Primary research question this composition supports (retrospective,
descriptive only): "Historically, how did this strategy's failed BUY
signals differ from its non-failed BUY signals in their subsequent
outcomes and in the market/strategy context present when those signals
fired?" It does NOT answer "why did the strategy fail" and must NEVER be
extended with causal, predictive, confidence, statistical-significance,
or strategy-optimization language -- see the identical warnings already
on Phase 4B (`comparison.py`) and Phase 4C (`context.py`), which this
module composes unchanged.

Two information classes, kept structurally distinct (never merged into a
single ambiguous "features" object):
  - RETROSPECTIVE OUTCOME information (`outcome_comparison`, Phase 4B) --
    10-bar forward return/MAE/MFE, which use post-signal observations by
    design (Phase 4A/4B's own accepted boundary).
  - SIGNAL-TIME CONTEXT (`context_analysis`, Phase 4C) -- RSI/volatility/
    regime/trend distances, which are point-in-time and must never use
    post-signal information (Phase 4C's own accepted boundary; see its
    module docstring for the point-in-time isolation guarantee).

Frozen population definitions (NOT redefined here): FAILED = Phase 4A
`classification == NEGATIVE`; NON_FAILED = `POSITIVE` or `BREAKEVEN`;
UNAVAILABLE = incomplete 10-bar outcome -- counted explicitly, excluded
from both `outcome_comparison`/`context_analysis` comparison summaries
(that exclusion already happened in Phase 4B/4C; Phase 4D only re-verifies
it was applied consistently).

Zero coupling to FastAPI, Pydantic, SQLAlchemy, pandas, numpy, scipy,
sklearn, any AI/LLM component, or the frontend -- pure Python domain
composition (grep-verified).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import InvestigationInputInvalidError
from app.investigation.comparison import FailurePopulationComparison
from app.investigation.context import FailureContextDataset
from app.investigation.models import SignalInvestigationDataset


@dataclass(frozen=True)
class StrategyFailureInvestigation:
    """The complete Phase 4D composed result for one symbol/strategy.

    `provider_symbol`/`interval`/`strategy_id`/`strategy_name` and the
    five population counts are cross-validated (see
    `build_strategy_failure_investigation`) against Phase 4A (the
    authoritative population source) and against Phase 4B's/4C's own
    declared counts -- they are not merely copied from one arbitrary
    upstream object.

    `outcome_comparison` (Phase 4B `FailurePopulationComparison`) and
    `context_analysis` (Phase 4C `FailureContextDataset`) are embedded
    UNCHANGED -- every nested value (means, medians, worst/best MAE/MFE,
    RSI/volatility/regime/trend-distance summaries, and per-signal
    `context_analysis.observations` for traceability) is the exact object
    Phase 4B/4C already produced. Phase 4D never recomputes or duplicates
    any of it.
    """

    provider_symbol: str
    interval: str
    strategy_id: str
    strategy_name: str

    total_signal_count: int
    eligible_count: int
    failed_count: int
    non_failed_count: int
    unavailable_count: int

    outcome_comparison: FailurePopulationComparison
    context_analysis: FailureContextDataset


def build_strategy_failure_investigation(
    investigation_dataset: SignalInvestigationDataset,
    outcome_comparison: FailurePopulationComparison,
    context_analysis: FailureContextDataset,
) -> StrategyFailureInvestigation:
    """Compose an accepted Phase 4A `SignalInvestigationDataset`, Phase 4B
    `FailurePopulationComparison`, and Phase 4C `FailureContextDataset`
    (all already built for the SAME symbol/strategy/history) into one
    `StrategyFailureInvestigation`.

    Phase 4A is treated as the authoritative population source (it is the
    original classification of every historical signal); `failed_count`/
    `non_failed_count`/`eligible_count` are derived from it exactly once
    and then cross-checked against Phase 4B's and Phase 4C's own declared
    counts. Does not mutate any input and does not reorder observations.

    Raises InvestigationInputInvalidError for: a provider_symbol/interval/
    strategy_id/strategy_name mismatch between any pair of the three
    inputs; any population-count disagreement between the three inputs
    (see module docstring); or a Phase 4C `context_analysis.observations`
    sequence whose (signal_date, classification) pairs do not match Phase
    4A's `investigation_dataset.observations` sequence exactly, in order
    (no silent dropping, reordering, or nearest-date matching).
    """
    _validate_metadata_consistency(investigation_dataset, outcome_comparison, context_analysis)

    failed_count = investigation_dataset.negative_count
    non_failed_count = investigation_dataset.positive_count + investigation_dataset.breakeven_count
    eligible_count = failed_count + non_failed_count
    total_signal_count = investigation_dataset.total_signal_count
    unavailable_count = investigation_dataset.unavailable_count

    if total_signal_count != eligible_count + unavailable_count:
        raise InvestigationInputInvalidError(
            f"Phase 4A dataset is internally inconsistent: total_signal_count={total_signal_count} but "
            f"eligible_count ({eligible_count}) + unavailable_count ({unavailable_count}) = "
            f"{eligible_count + unavailable_count}."
        )

    _validate_population_counts(
        "Phase 4B",
        outcome_comparison.total_signal_count,
        outcome_comparison.eligible_count,
        outcome_comparison.unavailable_count,
        outcome_comparison.failed.count,
        outcome_comparison.non_failed.count,
        total_signal_count,
        eligible_count,
        unavailable_count,
        failed_count,
        non_failed_count,
    )
    _validate_population_counts(
        "Phase 4C",
        context_analysis.total_signal_count,
        context_analysis.eligible_count,
        context_analysis.unavailable_count,
        context_analysis.failed_count,
        context_analysis.non_failed_count,
        total_signal_count,
        eligible_count,
        unavailable_count,
        failed_count,
        non_failed_count,
    )

    _validate_observation_alignment(investigation_dataset, context_analysis)

    return StrategyFailureInvestigation(
        provider_symbol=investigation_dataset.provider_symbol,
        interval=investigation_dataset.interval,
        strategy_id=investigation_dataset.strategy_id,
        strategy_name=investigation_dataset.strategy_name,
        total_signal_count=total_signal_count,
        eligible_count=eligible_count,
        failed_count=failed_count,
        non_failed_count=non_failed_count,
        unavailable_count=unavailable_count,
        outcome_comparison=outcome_comparison,
        context_analysis=context_analysis,
    )


def _validate_metadata_consistency(
    investigation_dataset: SignalInvestigationDataset,
    outcome_comparison: FailurePopulationComparison,
    context_analysis: FailureContextDataset,
) -> None:
    fields = ("provider_symbol", "interval", "strategy_id", "strategy_name")
    sources = {
        "Phase 4A": investigation_dataset,
        "Phase 4B": outcome_comparison,
        "Phase 4C": context_analysis,
    }
    for field in fields:
        values = {name: getattr(source, field) for name, source in sources.items()}
        if len(set(values.values())) > 1:
            raise InvestigationInputInvalidError(
                f"{field} mismatch across Phase 4 components: " + ", ".join(f"{name}={value!r}" for name, value in values.items())
            )


def _validate_population_counts(
    phase_label: str,
    reported_total: int,
    reported_eligible: int,
    reported_unavailable: int,
    reported_failed_count: int,
    reported_non_failed_count: int,
    expected_total: int,
    expected_eligible: int,
    expected_unavailable: int,
    expected_failed_count: int,
    expected_non_failed_count: int,
) -> None:
    if reported_total != expected_total:
        raise InvestigationInputInvalidError(
            f"{phase_label} total_signal_count={reported_total} does not match Phase 4A's total_signal_count="
            f"{expected_total}."
        )
    if reported_eligible != expected_eligible:
        raise InvestigationInputInvalidError(
            f"{phase_label} eligible_count={reported_eligible} does not match the Phase 4A-derived eligible_count="
            f"{expected_eligible}."
        )
    if reported_unavailable != expected_unavailable:
        raise InvestigationInputInvalidError(
            f"{phase_label} unavailable_count={reported_unavailable} does not match Phase 4A's unavailable_count="
            f"{expected_unavailable}."
        )
    if reported_failed_count != expected_failed_count:
        raise InvestigationInputInvalidError(
            f"{phase_label} failed population count={reported_failed_count} does not match Phase 4A's "
            f"negative_count={expected_failed_count}."
        )
    if reported_non_failed_count != expected_non_failed_count:
        raise InvestigationInputInvalidError(
            f"{phase_label} non_failed population count={reported_non_failed_count} does not match Phase 4A's "
            f"positive_count + breakeven_count={expected_non_failed_count}."
        )


def _validate_observation_alignment(
    investigation_dataset: SignalInvestigationDataset, context_analysis: FailureContextDataset
) -> None:
    expected_sequence = tuple((o.signal_date, o.classification) for o in investigation_dataset.observations)
    actual_sequence = tuple((o.signal_date, o.classification) for o in context_analysis.observations)

    if len(expected_sequence) != len(actual_sequence):
        raise InvestigationInputInvalidError(
            f"Phase 4C has {len(actual_sequence)} observation(s) but Phase 4A has "
            f"{len(expected_sequence)} -- every Phase 4A observation must correspond to exactly one Phase 4C "
            "context observation, in the same order."
        )
    if expected_sequence != actual_sequence:
        raise InvestigationInputInvalidError(
            "Phase 4C observation (signal_date, classification) sequence does not exactly match Phase 4A's -- "
            "no silent dropping, reordering, or reclassification is permitted between the two phases."
        )
