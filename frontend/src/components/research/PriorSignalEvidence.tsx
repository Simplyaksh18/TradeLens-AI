import type { AuditHorizonStatistics, HistoricalSignalEvidence } from '../../api/types'
import { formatInteger, formatPercent } from '../../utils/format'
import { Card, SectionLabel } from '../ui/Card'

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1 text-sm">
      <span className="text-[var(--text-tertiary)]">{label}</span>
      <span className="font-mono-tabular text-[var(--text-primary)]">{value}</span>
    </div>
  )
}

function HorizonPanel({ title, stats }: { title: string; stats: AuditHorizonStatistics }) {
  const noObservations = stats.eligible_outcome_count === 0
  return (
    <div>
      <SectionLabel>{title}</SectionLabel>
      <div className="mt-1">
        <DetailRow label="Eligible Outcomes" value={formatInteger(stats.eligible_outcome_count)} />
        <DetailRow label="Positive" value={formatInteger(stats.positive_count)} />
        <DetailRow label="Negative" value={formatInteger(stats.negative_count)} />
        <DetailRow label="Breakeven" value={formatInteger(stats.breakeven_count)} />
        <DetailRow
          label="Hit Rate"
          value={noObservations ? 'Not available' : formatPercent(stats.hit_rate)}
        />
        <DetailRow
          label="Average Return"
          value={noObservations ? 'Not available' : formatPercent(stats.average_return, { signed: true })}
        />
      </div>
    </div>
  )
}

/** Phase 3A: "Prior Strategy Signals" -- same symbol + strategy + BUY +
 * `signal_date < audit_date` within the requested evidence window. This
 * frozen V1 term is used verbatim -- never "Similar Signals" or
 * "Comparable Market Conditions" (there is no similarity/regime matching
 * in V1; see CLAUDE.md Phase 3A). A null hit_rate/average_return (zero
 * eligible observations) is shown as "Not available", never as 0%. */
export function PriorSignalEvidence({ evidence }: { evidence: HistoricalSignalEvidence }) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between">
        <SectionLabel>Prior Strategy Signals</SectionLabel>
        <span className="text-sm font-mono-tabular text-[var(--text-primary)]">
          {formatInteger(evidence.prior_signal_count)} prior signal(s)
        </span>
      </div>

      {evidence.prior_signal_count === 0 ? (
        <p className="mt-2 text-sm text-[var(--text-tertiary)]">
          No prior BUY signals for this symbol/strategy within the selected evidence window.
        </p>
      ) : (
        <div className="mt-2 grid grid-cols-1 gap-x-6 sm:grid-cols-2 divide-y divide-[var(--border)] sm:divide-y-0">
          <HorizonPanel title="5 Trading Bars Forward" stats={evidence.five_bar} />
          <HorizonPanel title="10 Trading Bars Forward" stats={evidence.ten_bar} />
        </div>
      )}
    </Card>
  )
}
