import type { FailurePopulationComparison } from '../../api/types'
import { Card, SectionLabel } from '../ui/Card'
import { ComparisonTable, type ComparisonRow } from '../tables/ComparisonTable'
import { formatInteger, formatPercent } from '../../utils/format'

function pct(value: number | null): string {
  return value === null ? 'Not available' : formatPercent(value, { signed: true })
}

/** Phase 4B: retrospective outcome comparison, rendered verbatim from the
 * backend `outcome_comparison` -- percentage formatting is the ONLY
 * transformation applied (decimal fraction -> percentage string); no
 * average/median/worst/best is (re)computed here, and no derived
 * difference or "winner" column is added (see CLAUDE.md Phase 4F). MAE
 * values are never abs()'d -- their sign is preserved exactly as
 * returned. */
export function OutcomeComparison({ comparison }: { comparison: FailurePopulationComparison }) {
  const { failed, non_failed: nonFailed } = comparison

  const rows: ComparisonRow[] = [
    { label: 'Signals', failed: formatInteger(failed.count), nonFailed: formatInteger(nonFailed.count) },
    { label: 'Average 10D Return', failed: pct(failed.average_forward_return_10d), nonFailed: pct(nonFailed.average_forward_return_10d) },
    { label: 'Median 10D Return', failed: pct(failed.median_forward_return_10d), nonFailed: pct(nonFailed.median_forward_return_10d) },
    { label: 'Average MAE', failed: pct(failed.average_mae_10d), nonFailed: pct(nonFailed.average_mae_10d) },
    { label: 'Median MAE', failed: pct(failed.median_mae_10d), nonFailed: pct(nonFailed.median_mae_10d) },
    { label: 'Worst MAE', failed: pct(failed.worst_mae_10d), nonFailed: pct(nonFailed.worst_mae_10d) },
    { label: 'Average MFE', failed: pct(failed.average_mfe_10d), nonFailed: pct(nonFailed.average_mfe_10d) },
    { label: 'Median MFE', failed: pct(failed.median_mfe_10d), nonFailed: pct(nonFailed.median_mfe_10d) },
    { label: 'Best MFE', failed: pct(failed.best_mfe_10d), nonFailed: pct(nonFailed.best_mfe_10d) },
  ]

  return (
    <Card className="p-4">
      <SectionLabel>Retrospective Outcome Comparison</SectionLabel>
      <p className="mt-1 text-xs text-[var(--text-tertiary)]">Observed after each historical signal.</p>
      <div className="mt-3">
        <ComparisonTable rows={rows} />
      </div>

      {failed.count === 0 && (
        <p className="mt-2 text-xs text-[var(--text-tertiary)]">No failed signals were present in this research window.</p>
      )}
      {nonFailed.count === 0 && (
        <p className="mt-2 text-xs text-[var(--text-tertiary)]">No non-failed signals were present in this research window.</p>
      )}
    </Card>
  )
}
