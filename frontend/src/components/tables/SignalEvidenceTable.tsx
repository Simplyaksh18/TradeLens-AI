import { useMemo, useState } from 'react'
import type { SignalFailureContext, MarketRegime } from '../../api/types'
import { ClassificationBadge } from '../ui/ClassificationBadge'
import { NoDataState } from '../ui/States'
import { formatDate, formatNumber, formatPercent } from '../../utils/format'

const REGIME_LABEL: Record<MarketRegime, string> = {
  BULLISH_TREND: 'Bullish Trend',
  BEARISH_TREND: 'Bearish Trend',
  TRANSITIONAL: 'Transitional',
  INSUFFICIENT_DATA: 'Insufficient Data',
}

type RowFilter = 'ALL' | 'FAILED' | 'NON_FAILED' | 'UNAVAILABLE'

const FILTERS: { value: RowFilter; label: string }[] = [
  { value: 'ALL', label: 'All' },
  { value: 'FAILED', label: 'Failed' },
  { value: 'NON_FAILED', label: 'Non-Failed' },
  { value: 'UNAVAILABLE', label: 'Unavailable' },
]

function matchesFilter(observation: SignalFailureContext, filter: RowFilter): boolean {
  if (filter === 'ALL') return true
  if (filter === 'FAILED') return observation.classification === 'NEGATIVE'
  if (filter === 'NON_FAILED') return observation.classification === 'POSITIVE' || observation.classification === 'BREAKEVEN'
  return observation.classification === 'UNAVAILABLE'
}

/** Phase 4C per-signal evidence table. Filtering here is VIEW-ONLY -- it
 * changes which already-returned rows are displayed, never which rows
 * exist, and never touches the population/outcome/context summary
 * sections elsewhere on the page (see CLAUDE.md Phase 4F: filtering rows
 * must never be mistaken for filtering the statistical summaries).
 * Backend source order is preserved by default -- never re-sorted. */
export function SignalEvidenceTable({ observations }: { observations: SignalFailureContext[] }) {
  const [filter, setFilter] = useState<RowFilter>('ALL')
  const filtered = useMemo(() => observations.filter((o) => matchesFilter(o, filter)), [observations, filter])

  if (observations.length === 0) {
    return <NoDataState message="No historical BUY signals in this research window." />
  }

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter displayed rows">
        {FILTERS.map((f) => (
          <button
            key={f.value}
            type="button"
            onClick={() => setFilter(f.value)}
            aria-pressed={filter === f.value}
            className={`rounded-full border px-2.5 py-1 text-xs font-medium transition-colors ${
              filter === f.value
                ? 'border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--accent-strong)]'
                : 'border-[var(--border)] text-[var(--text-secondary)] hover:bg-[var(--surface-2)]'
            }`}
          >
            {f.label}
          </button>
        ))}
        <span className="ml-auto text-xs text-[var(--text-tertiary)]">
          {filtered.length} of {observations.length} rows
        </span>
      </div>
      <p className="mb-2 text-xs text-[var(--text-tertiary)]">
        This filter changes only which rows are displayed below. It does not affect the population, outcome, or
        context comparison figures above, which always reflect the complete research window.
      </p>

      <div className="max-h-[480px] overflow-auto rounded-md border border-[var(--border)]">
        <table className="w-full min-w-[880px] text-sm">
          <thead className="sticky top-0 z-10">
            <tr className="border-b border-[var(--border)] bg-[var(--surface-2)] text-left text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
              <th className="px-3 py-2 font-medium">Signal Date</th>
              <th className="px-3 py-2 font-medium">Classification</th>
              <th className="px-3 py-2 font-medium">Regime</th>
              <th className="px-3 py-2 font-medium">RSI14</th>
              <th className="px-3 py-2 font-medium">20-Bar Volatility</th>
              <th className="px-3 py-2 font-medium">Close</th>
              <th className="px-3 py-2 font-medium">SMA20</th>
              <th className="px-3 py-2 font-medium">SMA50</th>
              <th className="px-3 py-2 font-medium">Close vs SMA20</th>
              <th className="px-3 py-2 font-medium">SMA20 vs SMA50</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((o) => (
              <tr key={o.signal_date} className="border-b border-[var(--border)] last:border-0">
                <td className="px-3 py-1.5 font-mono-tabular whitespace-nowrap">{formatDate(o.signal_date)}</td>
                <td className="px-3 py-1.5">
                  <ClassificationBadge classification={o.classification} />
                </td>
                <td className="px-3 py-1.5 text-[var(--text-secondary)]">{REGIME_LABEL[o.regime]}</td>
                <td className="px-3 py-1.5 font-mono-tabular">{formatNumber(o.rsi14)}</td>
                <td className="px-3 py-1.5 font-mono-tabular">
                  {o.annualized_realized_volatility_20 === null ? 'Not available' : formatPercent(o.annualized_realized_volatility_20)}
                </td>
                <td className="px-3 py-1.5 font-mono-tabular">{formatNumber(o.close)}</td>
                <td className="px-3 py-1.5 font-mono-tabular">{formatNumber(o.sma20)}</td>
                <td className="px-3 py-1.5 font-mono-tabular">{formatNumber(o.sma50)}</td>
                <td className="px-3 py-1.5 font-mono-tabular">{formatPercent(o.close_above_sma20_fraction, { signed: true })}</td>
                <td className="px-3 py-1.5 font-mono-tabular">{formatPercent(o.sma20_above_sma50_fraction, { signed: true })}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
