import { useState, type FormEvent, type KeyboardEvent } from 'react'
import { Search } from 'lucide-react'
import { Card } from '../ui/Card'

const SUGGESTED_QUESTIONS = [
  'What are the exact BUY conditions for Trend + Momentum v1?',
  'Audit RELIANCE on 2024-06-13 and explain the decision.',
  'Investigate RELIANCE strategy failures from 2023-01-01 to 2024-06-30.',
  'Summarize RELIANCE backtest performance from 2023-01-01 to 2024-06-30.',
  'What does an unavailable 10-bar outcome mean?',
]

interface ResearchQuestionFormProps {
  onSubmit: (question: string) => void
  loading: boolean
}

/** Multiline free-text question input -- no chat bubbles, no history, one
 * request per submission. Ctrl/Cmd+Enter submits alongside the button. */
export function ResearchQuestionForm({ onSubmit, loading }: ResearchQuestionFormProps) {
  const [question, setQuestion] = useState('')

  function submitIfValid() {
    const trimmed = question.trim()
    if (!trimmed || loading) return
    onSubmit(question)
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault()
    submitIfValid()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
      event.preventDefault()
      submitIfValid()
    }
  }

  return (
    <Card className="p-4">
      <form onSubmit={handleSubmit}>
        <label htmlFor="research-question" className="text-xs text-[var(--text-tertiary)]">
          Research question
        </label>
        <textarea
          id="research-question"
          value={question}
          onChange={(event) => setQuestion(event.target.value)}
          onKeyDown={handleKeyDown}
          disabled={loading}
          rows={3}
          maxLength={2000}
          placeholder="Ask TradeLens to investigate its deterministic strategy evidence and documented methodology..."
          className="mt-1 w-full resize-y rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-2 text-sm text-[var(--text-primary)] outline-none focus:border-[var(--accent)] disabled:opacity-60"
        />

        <div className="mt-3 flex flex-wrap items-center gap-2">
          <button
            type="submit"
            disabled={loading || !question.trim()}
            className="inline-flex items-center gap-1.5 rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-all hover:bg-[var(--accent-strong)] active:scale-[0.98] disabled:opacity-50 disabled:hover:bg-[var(--accent)] disabled:active:scale-100"
          >
            <Search size={14} aria-hidden="true" />
            Run Research
          </button>
          <span className="text-xs text-[var(--text-tertiary)]">Ctrl/Cmd + Enter to submit</span>
        </div>
      </form>

      <div className="mt-4">
        <span className="text-xs text-[var(--text-tertiary)]">Suggested questions</span>
        <div className="mt-1.5 flex flex-wrap gap-1.5">
          {SUGGESTED_QUESTIONS.map((suggestion) => (
            <button
              key={suggestion}
              type="button"
              disabled={loading}
              onClick={() => {
                setQuestion(suggestion)
                onSubmit(suggestion)
              }}
              className="rounded-full border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1 text-xs text-[var(--text-secondary)] transition-colors hover:border-[var(--accent)] hover:text-[var(--text-primary)] disabled:opacity-50"
            >
              {suggestion}
            </button>
          ))}
        </div>
      </div>
    </Card>
  )
}
