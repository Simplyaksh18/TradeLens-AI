import { STRATEGY_METADATA } from '../../utils/strategyMetadata'

const TREND_MOMENTUM_V1 = STRATEGY_METADATA.trend_momentum_v1

/** Compact, collapsible methodology disclosure. Purely explanatory/static
 * copy -- these definitions are never (re)calculated here; the actual
 * classification/comparison values always come from the Phase 4E API
 * response. Uses a native <details>/<summary> element, matching the
 * existing StrategyRulesDisclosure pattern (see CLAUDE.md Phase 3E). */
export function InvestigationMethodology() {
  return (
    <details className="group rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-4 py-2 text-sm">
      <summary className="cursor-pointer select-none text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
        Investigation Methodology
      </summary>

      <div className="mt-3 space-y-3 pb-1 text-xs text-[var(--text-secondary)]">
        <div>
          <p className="font-semibold text-[var(--text-primary)]">Failure classification</p>
          <p className="mt-0.5">
            A BUY signal with a strictly negative accepted 10-trading-bar forward return is classified{' '}
            <span className="font-medium text-[var(--text-primary)]">Failed</span>.
          </p>
        </div>
        <div>
          <p className="font-semibold text-[var(--text-primary)]">Non-Failed</p>
          <p className="mt-0.5">A positive or breakeven accepted 10-bar return.</p>
        </div>
        <div>
          <p className="font-semibold text-[var(--text-primary)]">Unavailable</p>
          <p className="mt-0.5">Insufficient forward trading bars inside the selected research window.</p>
        </div>
        <div>
          <p className="font-semibold text-[var(--text-primary)]">Retrospective Outcome</p>
          <p className="mt-0.5">Uses post-signal prices by definition -- this is hindsight, not information available at signal time.</p>
        </div>
        <div>
          <p className="font-semibold text-[var(--text-primary)]">Signal-Time Context</p>
          <p className="mt-0.5">Uses only information available at the signal date.</p>
        </div>

        <div>
          <p className="font-semibold text-[var(--text-primary)]">{TREND_MOMENTUM_V1.strategyName}</p>
          <div className="mt-1 rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3 font-mono-tabular text-xs leading-relaxed text-[var(--text-primary)]">
            <div>BUY requires</div>
            {TREND_MOMENTUM_V1.conditions.map((condition, i) => (
              <div key={condition}>{i === 0 ? condition : `AND ${condition}`}</div>
            ))}
          </div>
        </div>

        <p className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 italic">
          Historical associations are descriptive and do not establish causation or predict future outcomes.
        </p>
      </div>
    </details>
  )
}
