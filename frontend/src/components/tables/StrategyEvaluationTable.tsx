import { useMemo, useState } from 'react'
import type { StrategyDecision, StrategyEvaluation } from '../../api/types'
import { DecisionChip, ConditionOutcome } from '../ui/DecisionChip'
import { formatDate } from '../../utils/format'

function findCondition(evaluation: StrategyEvaluation, conditionId: string) {
  return evaluation.conditions.find((c) => c.condition_id === conditionId)
}

type DecisionFilter = 'ALL' | StrategyDecision

const FILTERS: { value: DecisionFilter; label: string }[] = [
  { value: 'ALL', label: 'All' },
  { value: 'BUY', label: 'Buy' },
  { value: 'NO_SIGNAL', label: 'No Signal' },
  { value: 'INSUFFICIENT_DATA', label: 'Insufficient Data' },
]

interface StrategyEvaluationTableProps {
  evaluations: StrategyEvaluation[]
  selectedDate?: string | null
  onSelect?: (evaluation: StrategyEvaluation) => void
}

export function StrategyEvaluationTable({ evaluations, selectedDate, onSelect }: StrategyEvaluationTableProps) {
  // View-only filter — never mutates or drops data, just narrows what's
  // displayed. Defaults to "All" so INSUFFICIENT_DATA history is never
  // hidden by default (see CLAUDE.md: data must remain inspectable).
  const [filter, setFilter] = useState<DecisionFilter>('ALL')
  const filtered = useMemo(
    () => (filter === 'ALL' ? evaluations : evaluations.filter((e) => e.decision === filter)),
    [evaluations, filter],
  )

  return (
    <div>
      <div className="mb-2 flex flex-wrap items-center gap-1.5" role="group" aria-label="Filter by decision">
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
          {filtered.length} of {evaluations.length} rows
        </span>
      </div>

      <div className="max-h-[420px] overflow-auto rounded-md border border-[var(--border)]">
        <table className="w-full min-w-[560px] text-sm">
          <thead className="sticky top-0 z-10">
            <tr className="border-b border-[var(--border)] bg-[var(--surface-2)] text-left text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
              <th className="px-3 py-2 font-medium">Date</th>
              <th className="px-3 py-2 font-medium">Decision</th>
              <th className="px-3 py-2 font-medium">Close &gt; SMA20</th>
              <th className="px-3 py-2 font-medium">SMA20 &gt; SMA50</th>
              <th className="px-3 py-2 font-medium">RSI Range</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((evaluation) => {
              const sufficient = evaluation.decision !== 'INSUFFICIENT_DATA'
              const closeCondition = findCondition(evaluation, 'close_above_sma20')
              const smaCondition = findCondition(evaluation, 'sma20_above_sma50')
              const rsiCondition = findCondition(evaluation, 'rsi_in_range')
              const isSelected = selectedDate === evaluation.date

              return (
                <tr
                  key={evaluation.date}
                  onClick={() => sufficient && onSelect?.(evaluation)}
                  className={`border-b border-[var(--border)] last:border-0 ${
                    sufficient ? 'cursor-pointer hover:bg-[var(--surface-2)]' : 'opacity-70'
                  } ${isSelected ? 'bg-[var(--accent-soft)]' : ''}`}
                >
                  <td className="px-3 py-1.5 font-mono-tabular whitespace-nowrap">{formatDate(evaluation.date)}</td>
                  <td className="px-3 py-1.5">
                    <DecisionChip decision={evaluation.decision} />
                  </td>
                  <td className="px-3 py-1.5">{closeCondition ? <ConditionOutcome passed={closeCondition.passed} /> : '—'}</td>
                  <td className="px-3 py-1.5">{smaCondition ? <ConditionOutcome passed={smaCondition.passed} /> : '—'}</td>
                  <td className="px-3 py-1.5">{rsiCondition ? <ConditionOutcome passed={rsiCondition.passed} /> : '—'}</td>
                </tr>
              )
            })}
          </tbody>
        </table>
      </div>
    </div>
  )
}
