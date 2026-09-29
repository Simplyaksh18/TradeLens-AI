import { ShieldAlert } from 'lucide-react'
import { Card } from '../ui/Card'

/** Section D: persistent, concise research-boundary copy -- kept short so
 * it doesn't overwhelm the page. */
export function ResearchBoundaries() {
  return (
    <Card className="p-3">
      <div className="flex items-start gap-2 text-xs text-[var(--text-tertiary)]">
        <ShieldAlert size={14} className="mt-0.5 shrink-0" aria-hidden="true" />
        <p>
          All financial calculations come from TradeLens's deterministic engines -- the AI only synthesizes and
          explains that evidence. Historical/backtested results do not predict future performance. Failure
          associations describe correlation, not causation. Retrospective/hindsight evidence is always shown
          separately from what was knowable at the time of a decision.
        </p>
      </div>
    </Card>
  )
}
