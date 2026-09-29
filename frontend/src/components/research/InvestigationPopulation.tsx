import type { StrategyFailureInvestigationResponse } from '../../api/types'
import { Card, SectionLabel } from '../ui/Card'
import { formatInteger } from '../../utils/format'

function PopulationCard({ label, value }: { label: string; value: number }) {
  return (
    <Card className="p-4">
      <SectionLabel>{label}</SectionLabel>
      <p className="mt-2 text-2xl font-semibold font-mono-tabular text-[var(--text-primary)]">{formatInteger(value)}</p>
    </Card>
  )
}

/** Phase 4E population counts, rendered verbatim from the backend --
 * total_signal_count/eligible_count/failed_count/non_failed_count/
 * unavailable_count. Deliberately does NOT compute a failure/success
 * percentage: the accepted API does not expose one, so none is derived
 * here (see CLAUDE.md Phase 4F). */
export function InvestigationPopulation({ investigation }: { investigation: StrategyFailureInvestigationResponse }) {
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
      <PopulationCard label="Total BUY Signals" value={investigation.total_signal_count} />
      <PopulationCard label="Eligible 10-Bar Outcomes" value={investigation.eligible_count} />
      <PopulationCard label="Failed" value={investigation.failed_count} />
      <PopulationCard label="Non-Failed" value={investigation.non_failed_count} />
      <PopulationCard label="Unavailable" value={investigation.unavailable_count} />
    </div>
  )
}
