import { History } from 'lucide-react'
import type { AuditToolEvidence } from '../../api/types'
import { DecisionChip, ConditionOutcome } from '../ui/DecisionChip'
import { formatPercent } from '../../utils/format'
import { SectionLabel } from '../ui/Card'

function semanticClass(value: number | null): string {
  if (value === null || value === 0) return 'text-[var(--text-primary)]'
  return value > 0 ? 'text-[var(--positive)]' : 'text-[var(--negative)]'
}

/** Generic reason derivation -- uses ONLY values already present in the
 * accepted tool result (`decision`, `available_forward_bars`), never an
 * invented rule. `forward_return_10d` is null in exactly two distinct
 * situations that must not be conflated (see CLAUDE.md "Audit Contract"):
 * the audited decision was not BUY (no retrospective outcome exists at
 * all -- `available_forward_bars` is also null), or the decision WAS BUY
 * but fewer than 10 forward trading bars exist yet in the requested range
 * (`available_forward_bars` is a number less than 10). */
function hindsightUnavailableReason(evidence: AuditToolEvidence): string | null {
  const { forward_return_10d, available_forward_bars } = evidence.retrospective_hindsight
  if (forward_return_10d !== null) return null
  if (evidence.decision !== 'BUY') {
    return `No retrospective outcome applies because the audited decision was ${evidence.decision}, not BUY.`
  }
  return available_forward_bars !== null
    ? `The 10-bar retrospective outcome is not yet available -- only ${available_forward_bars} of 10 required forward trading bars exist in the requested date range.`
    : 'The 10-bar retrospective outcome is not yet available in the requested date range.'
}

/** Phase 5E: preserves the Phase 5C `audit_strategy_decision` tool's
 * accepted 4-part semantic boundary (see CLAUDE.md "Phase 5C final
 * hardening -- audit semantic boundary") as three visually SEPARATE
 * blocks. DECISION EVIDENCE is the sole, authoritative source of the
 * decision; POINT-IN-TIME CONTEXT is descriptive only; RETROSPECTIVE /
 * HINDSIGHT is never merged into "why BUY" -- mirrors the same dashed-
 * border hindsight treatment already established for the Strategy
 * Auditor page (`RetrospectiveOutcome.tsx`). Every value is rendered
 * verbatim from the tool result; nothing here is recalculated. */
export function AuditEvidenceBoundary({ evidence }: { evidence: AuditToolEvidence }) {
  return (
    <div className="space-y-3">
      <div>
        <div className="flex items-center justify-between">
          <SectionLabel>Decision Evidence</SectionLabel>
          <DecisionChip decision={evidence.decision} />
        </div>
        <p className="mt-1 text-xs text-[var(--text-tertiary)]">
          The decision is determined ONLY by these conditions -- nothing below this block influences it.
        </p>
        <div className="mt-2 space-y-1.5">
          {evidence.decision_evidence.map((condition) => (
            <div key={condition.condition_id} className="rounded border border-[var(--border)] p-2">
              <div className="flex items-center justify-between gap-2 text-xs font-medium">
                <span>{condition.description}</span>
                <ConditionOutcome passed={condition.passed} />
              </div>
            </div>
          ))}
        </div>
      </div>

      <div className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3">
        <SectionLabel>Point-in-Time Context</SectionLabel>
        <p className="mt-1 text-xs text-[var(--text-tertiary)]">
          Descriptive context only -- does not determine, justify, or explain the decision above.
        </p>
        <dl className="mt-2 grid grid-cols-2 gap-x-4 gap-y-1 text-xs">
          <div className="flex justify-between gap-2">
            <dt className="text-[var(--text-tertiary)]">Prior signals</dt>
            <dd className="font-mono-tabular">{evidence.point_in_time_context.prior_signal_count}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-[var(--text-tertiary)]">Regime</dt>
            <dd className="font-mono-tabular">{evidence.point_in_time_context.regime}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-[var(--text-tertiary)]">5-Bar hit rate</dt>
            <dd className="font-mono-tabular">{formatPercent(evidence.point_in_time_context.five_bar_hit_rate)}</dd>
          </div>
          <div className="flex justify-between gap-2">
            <dt className="text-[var(--text-tertiary)]">10-Bar hit rate</dt>
            <dd className="font-mono-tabular">{formatPercent(evidence.point_in_time_context.ten_bar_hit_rate)}</dd>
          </div>
          <div className="flex justify-between gap-2 col-span-2">
            <dt className="text-[var(--text-tertiary)]">Realized volatility (20-bar, annualized)</dt>
            <dd className="font-mono-tabular">{formatPercent(evidence.point_in_time_context.annualized_realized_volatility_20)}</dd>
          </div>
        </dl>
      </div>

      <div className="rounded-md border-2 border-dashed border-[var(--warning)]/40 bg-[var(--warning-soft)] p-3">
        <div className="flex items-center gap-2">
          <History size={14} className="text-[var(--warning)]" aria-hidden="true" />
          <span className="text-[11px] font-bold uppercase tracking-wider text-[var(--warning)]">Hindsight</span>
        </div>
        <h4 className="mt-1 text-xs font-semibold text-[var(--text-primary)]">Retrospective / Hindsight</h4>
        {hindsightUnavailableReason(evidence) !== null ? (
          <p className="mt-2 text-xs text-[var(--text-secondary)]">{hindsightUnavailableReason(evidence)}</p>
        ) : (
          <>
            <div className="mt-2 flex items-baseline justify-between gap-3 rounded border border-[var(--warning)]/25 bg-[var(--surface-1)] px-2.5 py-2">
              <span className="text-xs text-[var(--text-secondary)]">10-Bar forward return</span>
              <span className={`font-mono-tabular text-sm font-semibold ${semanticClass(evidence.retrospective_hindsight.forward_return_10d)}`}>
                {formatPercent(evidence.retrospective_hindsight.forward_return_10d, { signed: true })}
              </span>
            </div>
            <p className="mt-2 text-xs text-[var(--text-secondary)]">{evidence.retrospective_hindsight.note}</p>
          </>
        )}
      </div>
    </div>
  )
}
