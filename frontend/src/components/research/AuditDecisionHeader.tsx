import type { StrategyAuditResponse } from '../../api/types'
import { DecisionChip } from '../ui/DecisionChip'
import { formatDate } from '../../utils/format'
import { Card } from '../ui/Card'

/** Top-of-page identity + decision. Deliberately shows only the backend's
 * exact BUY/NO_SIGNAL/INSUFFICIENT_DATA decision via `DecisionChip` — no
 * "Strong Buy"/confidence-score/investment-advice language is ever added
 * here (see CLAUDE.md Research/Educational Positioning). */
export function AuditDecisionHeader({ audit }: { audit: StrategyAuditResponse }) {
  return (
    <Card className="p-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
          <span className="text-lg font-semibold font-mono-tabular text-[var(--text-primary)]">
            {audit.provider_symbol}
          </span>
          <span className="text-sm text-[var(--text-secondary)]">{audit.strategy_name}</span>
          <span className="text-sm text-[var(--text-tertiary)]">Audit Date: {formatDate(audit.audit_date)}</span>
        </div>
        <DecisionChip decision={audit.evaluation.decision} />
      </div>
    </Card>
  )
}
