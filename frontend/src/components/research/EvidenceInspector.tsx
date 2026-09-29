import type { ConditionResult, StrategyEvaluation } from '../../api/types'
import { InsufficientHistoryState } from '../ui/States'
import { DecisionChip, ConditionOutcome } from '../ui/DecisionChip'
import { formatDate, formatNumber } from '../../utils/format'
import { SectionLabel } from '../ui/Card'

function ConditionRow({ condition }: { condition: ConditionResult }) {
  return (
    <div
      className={`rounded-md border p-3 ${
        condition.passed ? 'border-[var(--positive)]/25' : 'border-[var(--border)]'
      }`}
    >
      <div className="flex items-center justify-between gap-2 text-sm font-medium">
        <span>{condition.description}</span>
        <ConditionOutcome passed={condition.passed} />
      </div>
      <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs font-mono-tabular text-[var(--text-secondary)]">
        {condition.actual_values.map((value) => (
          <div key={value.name} className="flex justify-between gap-2">
            <dt className="text-[var(--text-tertiary)]">{value.name}</dt>
            <dd>{formatNumber(value.value)}</dd>
          </div>
        ))}
        {condition.reference_values.map((value) => (
          <div key={value.name} className="flex justify-between gap-2">
            <dt className="text-[var(--text-tertiary)]">{value.name}</dt>
            <dd>{formatNumber(value.value)}</dd>
          </div>
        ))}
        <div className="flex justify-between gap-2 col-span-2 border-t border-[var(--border)] pt-1 mt-1">
          <dt className="text-[var(--text-tertiary)]">Rule</dt>
          <dd>{condition.operator}</dd>
        </div>
      </dl>
    </div>
  )
}

export function EvidenceInspector({ evaluation }: { evaluation: StrategyEvaluation | null }) {
  if (!evaluation) {
    return <p className="text-sm text-[var(--text-tertiary)]">Select a date to inspect its strategy evidence.</p>
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <SectionLabel>Decision Evidence: {formatDate(evaluation.date)}</SectionLabel>
        <DecisionChip decision={evaluation.decision} />
      </div>

      {evaluation.decision === 'INSUFFICIENT_DATA' ? (
        <InsufficientHistoryState missing={evaluation.missing_inputs} />
      ) : (
        <div className="space-y-2">
          {evaluation.conditions.map((condition) => (
            <ConditionRow key={condition.condition_id} condition={condition} />
          ))}
        </div>
      )}
    </div>
  )
}
