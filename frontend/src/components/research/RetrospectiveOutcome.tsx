import { History } from 'lucide-react'
import type { SignalOutcome, StrategyDecision } from '../../api/types'
import { formatNumber, formatPercent } from '../../utils/format'

function DetailRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-3 py-1 text-sm">
      <span className="text-[var(--text-tertiary)]">{label}</span>
      <span className="font-mono-tabular text-[var(--text-primary)]">{value}</span>
    </div>
  )
}

/** Deliberately visually distinct (dashed border, warning-tinted surface,
 * a "HINDSIGHT" badge) from every point-in-time section on this page --
 * see CLAUDE.md Phase 3E "Point-in-Time vs Hindsight Design". This is the
 * Phase 2A `SignalOutcome` for the audit_date itself, reused verbatim; it
 * is never allowed to influence, or be mistaken for, information the
 * strategy possessed on audit_date. Present only when the audit decision
 * was BUY -- never fabricated for NO_SIGNAL/INSUFFICIENT_DATA. */
export function RetrospectiveOutcome({ outcome, decision }: { outcome: SignalOutcome | null; decision: StrategyDecision }) {
  return (
    <div className="rounded-md border-2 border-dashed border-[var(--warning)]/40 bg-[var(--warning-soft)] p-4">
      <div className="flex items-center gap-2">
        <History size={16} className="text-[var(--warning)]" aria-hidden="true" />
        <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--warning)]">Hindsight</span>
      </div>
      <h3 className="mt-1 text-sm font-semibold text-[var(--text-primary)]">Retrospective Outcome</h3>
      <p className="mt-1 text-xs text-[var(--text-secondary)]">
        Observed after the audit date. This information was not available to the strategy at the time.
      </p>

      {!outcome ? (
        <p className="mt-3 text-sm text-[var(--text-tertiary)]">
          {decision === 'BUY'
            ? 'No retrospective BUY outcome for this audit date.'
            : `No retrospective BUY outcome applies because the audited decision was ${decision}, not BUY.`}
        </p>
      ) : (
        <div className="mt-3">
          <DetailRow label="Reference Close" value={formatNumber(outcome.reference_close)} />
          <DetailRow
            label="5-Bar Forward Close"
            value={outcome.forward_close_5d === null ? 'Not yet available in the selected data range' : formatNumber(outcome.forward_close_5d)}
          />
          <DetailRow
            label="5-Bar Return"
            value={
              outcome.forward_return_5d === null
                ? 'Not yet available in the selected data range'
                : formatPercent(outcome.forward_return_5d, { signed: true })
            }
          />
          <DetailRow
            label="10-Bar Forward Close"
            value={outcome.forward_close_10d === null ? 'Not yet available in the selected data range' : formatNumber(outcome.forward_close_10d)}
          />
          <DetailRow
            label="10-Bar Return"
            value={
              outcome.forward_return_10d === null
                ? 'Not yet available in the selected data range'
                : formatPercent(outcome.forward_return_10d, { signed: true })
            }
          />
          <DetailRow
            label="10-Bar MAE"
            value={outcome.mae_10d === null ? 'Not yet available in the selected data range' : formatPercent(outcome.mae_10d, { signed: true })}
          />
          <DetailRow
            label="10-Bar MFE"
            value={outcome.mfe_10d === null ? 'Not yet available in the selected data range' : formatPercent(outcome.mfe_10d, { signed: true })}
          />
          <DetailRow label="Available Forward Bars" value={String(outcome.available_forward_bars)} />
        </div>
      )}
    </div>
  )
}
