import { Sparkles } from 'lucide-react'
import { Card, SectionLabel } from '../ui/Card'
import { MarkdownContent } from './MarkdownContent'
import type { ResearchStoppedReason } from '../../api/types'

const STOPPED_REASON_NOTE: Record<ResearchStoppedReason, string | null> = {
  final_answer: null,
  max_steps_reached: 'TradeLens reached its bounded research-step limit before finishing. Try a narrower question.',
  insufficient_evidence: 'TradeLens did not find sufficient deterministic evidence to answer this question.',
}

interface ResearchSynthesisProps {
  question: string
  answer: string
  stoppedReason: ResearchStoppedReason
}

/** Section A: the AI-generated explanation, clearly labeled as synthesis
 * grounded in deterministic TradeLens evidence -- never presented as an
 * independent "AI reasoning" or opinion. */
export function ResearchSynthesis({ question, answer, stoppedReason }: ResearchSynthesisProps) {
  const note = STOPPED_REASON_NOTE[stoppedReason]
  return (
    <Card className="p-4">
      <div className="flex items-center gap-1.5">
        <Sparkles size={14} className="text-[var(--accent)]" aria-hidden="true" />
        <SectionLabel>Research Synthesis</SectionLabel>
      </div>
      <p className="mt-1 text-xs text-[var(--text-tertiary)]">
        AI-generated synthesis grounded in the deterministic TradeLens evidence below -- not an independent opinion.
      </p>
      <p className="mt-3 text-xs text-[var(--text-tertiary)]">Question</p>
      <p className="text-sm text-[var(--text-secondary)]">{question}</p>
      <p className="mt-3 text-xs text-[var(--text-tertiary)]">Answer</p>
      <div className="mt-1">
        <MarkdownContent content={answer} />
      </div>
      {note && (
        <p role="status" className="mt-3 rounded-md border border-[var(--warning)]/30 bg-[var(--warning-soft)] px-3 py-2 text-xs text-[var(--warning)]">
          {note}
        </p>
      )}
    </Card>
  )
}
