import { Card, SectionLabel } from '../ui/Card'

const STEPS: { title: string; description: string }[] = [
  { title: '1. Historical BUY Signals', description: 'Every accepted historical BUY signal for this symbol and date range.' },
  {
    title: '2. 10-Bar Outcome Classification',
    description: 'Each signal is classified by its accepted 10-trading-bar forward return.',
  },
  { title: '3. Failed vs Non-Failed Comparison', description: 'Retrospective outcomes compared across the two populations.' },
  { title: '4. Signal-Time Context', description: 'Market and strategy conditions present when each signal fired, compared the same way.' },
]

/** Compact, static orientation strip -- four short steps, not a tutorial or
 * dashboard. Purely explanatory copy; nothing here is derived from the
 * Phase 4E API response. Definitions are the frozen Phase 4 v1 terms
 * (see CLAUDE.md Phase 4A) -- never a configurable/invented threshold. */
export function HowThisInvestigationWorks() {
  return (
    <Card className="p-4">
      <SectionLabel>How This Investigation Works</SectionLabel>
      <dl className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((step) => (
          <div key={step.title}>
            <dt className="text-sm font-medium text-[var(--text-primary)]">{step.title}</dt>
            <dd className="mt-1 text-xs text-[var(--text-secondary)]">{step.description}</dd>
          </div>
        ))}
      </dl>

      <dl className="mt-4 grid grid-cols-1 gap-3 border-t border-[var(--border)] pt-3 sm:grid-cols-3">
        <div>
          <dt className="text-xs font-semibold text-[var(--text-primary)]">Failed</dt>
          <dd className="mt-0.5 text-xs text-[var(--text-secondary)]">10-trading-bar forward return strictly negative.</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-[var(--text-primary)]">Non-Failed</dt>
          <dd className="mt-0.5 text-xs text-[var(--text-secondary)]">Positive or breakeven 10-bar outcome.</dd>
        </div>
        <div>
          <dt className="text-xs font-semibold text-[var(--text-primary)]">Unavailable</dt>
          <dd className="mt-0.5 text-xs text-[var(--text-secondary)]">
            Insufficient forward trading bars inside the selected research window.
          </dd>
        </div>
      </dl>
    </Card>
  )
}
