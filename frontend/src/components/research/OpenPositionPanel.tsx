import type { BacktestResultResponse, PerformanceAnalyticsResponse } from '../../api/types'
import { formatCurrency, formatDate, formatInteger, formatNumber } from '../../utils/format'
import { Card, SectionLabel } from '../ui/Card'

interface OpenPositionPanelProps {
  backtest: BacktestResultResponse
  analytics: PerformanceAnalyticsResponse | null
}

/** Reflects Phase 2B/2C execution state exactly as returned by the API —
 * never infers, fabricates, or closes a position in the frontend.
 * Pending entry/exit are explicit end-of-data execution states, not
 * errors (see CLAUDE.md Phase 2B). */
export function OpenPositionPanel({ backtest, analytics }: OpenPositionPanelProps) {
  const { open_position, pending_entry_signal_date } = backtest

  return (
    <Card className="p-4">
      <SectionLabel>Current Position</SectionLabel>

      {open_position && (
        <div className="mt-2 space-y-2">
          <div className="flex items-center justify-between">
            <span className="inline-flex items-center gap-1.5 rounded border border-[var(--positive)]/30 bg-[var(--positive-soft)] px-2 py-0.5 text-xs font-medium text-[var(--positive)]">
              Status: OPEN
            </span>
            <span className="text-sm font-mono-tabular text-[var(--text-primary)]">
              Unrealized P&L: {formatCurrency(analytics?.unrealized_pnl ?? null)}
            </span>
          </div>
          <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-sm">
            <dt className="text-[var(--text-tertiary)]">Entry Signal Date</dt>
            <dd className="text-right font-mono-tabular">{formatDate(open_position.entry_signal_date)}</dd>
            <dt className="text-[var(--text-tertiary)]">Entry Date</dt>
            <dd className="text-right font-mono-tabular">{formatDate(open_position.entry_date)}</dd>
            <dt className="text-[var(--text-tertiary)]">Entry Price</dt>
            <dd className="text-right font-mono-tabular">{formatNumber(open_position.entry_price)}</dd>
            <dt className="text-[var(--text-tertiary)]">Quantity</dt>
            <dd className="text-right font-mono-tabular">{formatInteger(open_position.quantity)}</dd>
          </dl>

          {open_position.pending_exit_signal_date && (
            <div className="rounded-md border border-[var(--warning)]/30 bg-[var(--warning-soft)] px-3 py-2 text-sm text-[var(--warning)]">
              <p className="font-medium">Pending Exit Signal ({formatDate(open_position.pending_exit_signal_date)})</p>
              <p className="mt-1 text-xs opacity-90">
                Exit condition occurred on the final available bar; no next trading bar was available for execution.
              </p>
            </div>
          )}
        </div>
      )}

      {!open_position && pending_entry_signal_date && (
        <div className="mt-2 rounded-md border border-[var(--warning)]/30 bg-[var(--warning-soft)] px-3 py-2 text-sm text-[var(--warning)]">
          <p className="font-medium">Pending Entry Signal ({formatDate(pending_entry_signal_date)})</p>
          <p className="mt-1 text-xs opacity-90">
            BUY occurred on the final available bar; no next trading bar was available for execution.
          </p>
        </div>
      )}

      {!open_position && !pending_entry_signal_date && (
        <p className="mt-2 text-sm text-[var(--text-secondary)]">No open position at end of selected period.</p>
      )}
    </Card>
  )
}
