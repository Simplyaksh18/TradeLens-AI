import { Card, SectionLabel } from '../ui/Card'

const STEPS: { title: string; description: string }[] = [
  { title: '1. Decision', description: 'Was it a BUY? Why or why not?' },
  { title: '2. Market Context', description: 'What regime and risk existed on that date?' },
  { title: '3. Prior Strategy Evidence', description: 'How did earlier BUY signals from this same strategy behave?' },
  {
    title: '4. Hindsight',
    description:
      'What actually happened after the audit date -- retrospective only, and not available to the strategy when the decision was made.',
  },
]

/** Compact, static orientation strip -- four short cards, not a tutorial or
 * dashboard. Purely explanatory copy; nothing here is derived from the
 * Phase 3D API response. */
export function HowThisAuditWorks() {
  return (
    <Card className="p-4">
      <SectionLabel>How This Audit Works</SectionLabel>
      <dl className="mt-3 grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {STEPS.map((step) => (
          <div key={step.title}>
            <dt className="text-sm font-medium text-[var(--text-primary)]">{step.title}</dt>
            <dd className="mt-1 text-xs text-[var(--text-secondary)]">{step.description}</dd>
          </div>
        ))}
      </dl>
    </Card>
  )
}
