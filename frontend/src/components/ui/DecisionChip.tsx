import { CheckCircle2, Circle, HelpCircle, MinusCircle } from 'lucide-react'
import type { StrategyDecision } from '../../api/types'

const DISPLAY_LABEL: Record<StrategyDecision, string> = {
  BUY: 'Buy',
  NO_SIGNAL: 'No Signal',
  INSUFFICIENT_DATA: 'Insufficient Data',
}

const STYLE: Record<StrategyDecision, string> = {
  BUY: 'bg-[var(--positive-soft)] text-[var(--positive)] border-[var(--positive)]/30',
  NO_SIGNAL: 'bg-[var(--neutral-chip)] text-[var(--text-secondary)] border-[var(--border-strong)]',
  INSUFFICIENT_DATA: 'bg-[var(--warning-soft)] text-[var(--warning)] border-[var(--warning)]/30',
}

const ICON: Record<StrategyDecision, typeof CheckCircle2> = {
  BUY: CheckCircle2,
  NO_SIGNAL: MinusCircle,
  INSUFFICIENT_DATA: HelpCircle,
}

/** Renders the backend's exact decision value with a readable label — never
 * remaps BUY/NO_SIGNAL/INSUFFICIENT_DATA into HOLD/SELL/confidence scores. */
export function DecisionChip({ decision }: { decision: StrategyDecision }) {
  const Icon = ICON[decision]
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium ${STYLE[decision]}`}
      data-decision={decision}
    >
      <Icon size={13} aria-hidden="true" />
      {DISPLAY_LABEL[decision]}
    </span>
  )
}

/** A failed strategy condition is an ordinary, expected outcome (the rule
 * evaluated false), never a software error — so FAIL deliberately does NOT
 * use `--negative` (reserved for genuine error states elsewhere in the app).
 * Muted/neutral styling keeps it legible as "not satisfied yet" rather than
 * something gone wrong. */
export function ConditionOutcome({ passed }: { passed: boolean }) {
  return passed ? (
    <span className="inline-flex items-center gap-1 text-[var(--positive)] text-xs font-medium">
      <CheckCircle2 size={14} aria-hidden="true" /> PASS
    </span>
  ) : (
    <span className="inline-flex items-center gap-1 text-[var(--text-tertiary)] text-xs font-medium">
      <Circle size={14} aria-hidden="true" /> FAIL
    </span>
  )
}
