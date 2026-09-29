import { MinusCircle, TrendingDown, TrendingUp, HelpCircle } from 'lucide-react'
import type { SignalInvestigationClassification } from '../../api/types'

// Deliberately NOT "Success"/"Failure" binary language beyond the frozen
// Phase 4 term "Failed" itself -- POSITIVE is labeled "Positive", never
// "Success", because NON_FAILED also includes BREAKEVEN and Phase 4
// deliberately avoids overstating outcomes (see CLAUDE.md Phase 4A/4F).
const LABEL: Record<SignalInvestigationClassification, string> = {
  NEGATIVE: 'Failed',
  POSITIVE: 'Positive',
  BREAKEVEN: 'Breakeven',
  UNAVAILABLE: 'Unavailable',
}

const STYLE: Record<SignalInvestigationClassification, string> = {
  NEGATIVE: 'bg-[var(--negative-soft)] text-[var(--negative)] border-[var(--negative)]/30',
  POSITIVE: 'bg-[var(--positive-soft)] text-[var(--positive)] border-[var(--positive)]/30',
  BREAKEVEN: 'bg-[var(--neutral-chip)] text-[var(--text-secondary)] border-[var(--border-strong)]',
  UNAVAILABLE: 'bg-[var(--warning-soft)] text-[var(--warning)] border-[var(--warning)]/30',
}

const ICON: Record<SignalInvestigationClassification, typeof TrendingUp> = {
  NEGATIVE: TrendingDown,
  POSITIVE: TrendingUp,
  BREAKEVEN: MinusCircle,
  UNAVAILABLE: HelpCircle,
}

/** Renders the backend's exact Phase 4A classification with a restrained
 * label/icon -- never remaps POSITIVE/NEGATIVE/BREAKEVEN/UNAVAILABLE into
 * "Success"/"Failure"/confidence language. */
export function ClassificationBadge({ classification }: { classification: SignalInvestigationClassification }) {
  const Icon = ICON[classification]
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded border px-2 py-0.5 text-xs font-medium ${STYLE[classification]}`}
      data-classification={classification}
    >
      <Icon size={13} aria-hidden="true" />
      {LABEL[classification]}
    </span>
  )
}
