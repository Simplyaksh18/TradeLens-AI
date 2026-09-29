import type { SignalOutcome } from '../../api/types'
import { formatDate, formatInteger, formatNumber, formatPercent } from '../../utils/format'
import { NoDataState } from '../ui/States'

/** Phase 2A research: "what happened after each historical BUY signal."
 * `reference_close` is deliberately labeled as such, never "Entry Price" —
 * it is observational, not an execution fill (that distinction belongs to
 * Phase 2B/the Trades tab). Consecutive BUY outcomes are never collapsed:
 * one row per backend outcome, in order. */
export function SignalOutcomesTable({ outcomes }: { outcomes: SignalOutcome[] }) {
  if (outcomes.length === 0) {
    return <NoDataState message="No BUY signal outcomes in this period." />
  }

  return (
    <div className="max-h-[420px] overflow-auto rounded-md border border-[var(--border)]">
      <table className="w-full min-w-[760px] text-sm">
        <thead className="sticky top-0 z-10">
          <tr className="border-b border-[var(--border)] bg-[var(--surface-2)] text-left text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th className="px-3 py-2 font-medium">Signal Date</th>
            <th className="px-3 py-2 font-medium" title="Observational reference price, not an execution fill">
              Reference Close
            </th>
            <th className="px-3 py-2 font-medium">+5D Close</th>
            <th className="px-3 py-2 font-medium">+5D Return</th>
            <th className="px-3 py-2 font-medium">+10D Close</th>
            <th className="px-3 py-2 font-medium">+10D Return</th>
            <th className="px-3 py-2 font-medium">10D MAE</th>
            <th className="px-3 py-2 font-medium">10D MFE</th>
            <th className="px-3 py-2 font-medium">Forward Bars</th>
          </tr>
        </thead>
        <tbody>
          {outcomes.map((o) => (
            <tr key={o.date} className="border-b border-[var(--border)] last:border-0">
              <td className="px-3 py-1.5 font-mono-tabular whitespace-nowrap">{formatDate(o.date)}</td>
              <td className="px-3 py-1.5 font-mono-tabular">{formatNumber(o.reference_close)}</td>
              <td className="px-3 py-1.5 font-mono-tabular">{formatNumber(o.forward_close_5d)}</td>
              <td className="px-3 py-1.5 font-mono-tabular">{formatPercent(o.forward_return_5d, { signed: true })}</td>
              <td className="px-3 py-1.5 font-mono-tabular">{formatNumber(o.forward_close_10d)}</td>
              <td className="px-3 py-1.5 font-mono-tabular">{formatPercent(o.forward_return_10d, { signed: true })}</td>
              <td className="px-3 py-1.5 font-mono-tabular">{formatPercent(o.mae_10d, { signed: true })}</td>
              <td className="px-3 py-1.5 font-mono-tabular">{formatPercent(o.mfe_10d, { signed: true })}</td>
              <td className="px-3 py-1.5 font-mono-tabular">{formatInteger(o.available_forward_bars)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
