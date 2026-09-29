import type { HistoricalSignalRisk as HistoricalSignalRiskData } from '../../api/types'
import { formatInteger, formatPercent } from '../../utils/format'
import { Card, SectionLabel } from '../ui/Card'

function DetailRow({ label, title, value }: { label: string; title?: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1 text-sm">
      <span className="text-[var(--text-tertiary)]" title={title}>
        {label}
      </span>
      <span className="font-mono-tabular text-[var(--text-primary)]">{value}</span>
    </div>
  )
}

/** Phase 3C: MAE/MFE aggregated over the same prior 10-bar-eligible
 * population as PriorSignalEvidence's "10 Trading Bars Forward" panel.
 * Signs are rendered exactly as returned by the API -- never abs()'d or
 * reinterpreted (see CLAUDE.md Phase 3C). */
export function HistoricalSignalRisk({ risk }: { risk: HistoricalSignalRiskData }) {
  const noObservations = risk.eligible_outcome_count === 0

  return (
    <Card className="p-4">
      <SectionLabel>Historical Signal Risk</SectionLabel>
      <p className="mt-1 text-xs text-[var(--text-tertiary)]">
        Maximum Adverse Excursion (MAE) is the worst move against a prior signal during its observed 10-bar forward
        window; Maximum Favorable Excursion (MFE) is the best move in favor of it over the same window.
      </p>

      <div className="mt-2">
        <DetailRow label="Eligible 10-Bar Outcomes" value={formatInteger(risk.eligible_outcome_count)} />
        <DetailRow
          label="Average MAE"
          title="Maximum Adverse Excursion, averaged across eligible prior signals"
          value={noObservations ? 'Not available' : formatPercent(risk.average_mae_10d, { signed: true })}
        />
        <DetailRow
          label="Worst MAE"
          title="Largest adverse excursion among eligible prior signals"
          value={noObservations ? 'Not available' : formatPercent(risk.worst_mae_10d, { signed: true })}
        />
        <DetailRow
          label="Average MFE"
          title="Maximum Favorable Excursion, averaged across eligible prior signals"
          value={noObservations ? 'Not available' : formatPercent(risk.average_mfe_10d, { signed: true })}
        />
        <DetailRow
          label="Best MFE"
          title="Largest favorable excursion among eligible prior signals"
          value={noObservations ? 'Not available' : formatPercent(risk.best_mfe_10d, { signed: true })}
        />
      </div>
    </Card>
  )
}
