import { PageHeader } from '../components/layout/PageHeader'
import { Card, SectionLabel } from '../components/ui/Card'
import { LoadingSkeleton, NothingSelectedState } from '../components/ui/States'
import { ApiError } from '../api/client'
import { ResearchQuestionForm } from '../components/research/ResearchQuestionForm'
import { ResearchSynthesis } from '../components/research/ResearchSynthesis'
import { ToolTraceList } from '../components/research/ToolTraceList'
import { KnowledgeSourcesList } from '../components/research/KnowledgeSourcesList'
import { ResearchBoundaries } from '../components/research/ResearchBoundaries'
import { useResearchQuery } from '../hooks/useResearchQuery'

const PROVIDER_UNAVAILABLE_CODES = new Set(['AI_PROVIDER_NOT_CONFIGURED', 'AI_PROVIDER_REQUEST_FAILED'])

/** AI_PROVIDER_RATE_LIMITED is a distinct backend error code (see
 * CLAUDE.md Phase 5E rate-limit diagnosis) for a genuine Groq 429 --
 * rendered with its own, more accurate copy rather than being collapsed
 * into the generic "provider unavailable" message. */
function researchErrorMessage(error: ApiError): { title: string; detail: string } {
  if (error.code === 'REQUEST_VALIDATION_ERROR' || error.code === 'INVALID_RESEARCH_QUESTION') {
    return { title: 'Invalid research question', detail: error.message }
  }
  if (error.code === 'SESSION_INVALID') {
    return {
      title: 'Your session has expired',
      detail: 'Please sign in again to use the Research Workspace.',
    }
  }
  if (error.code === 'AI_PROVIDER_RATE_LIMITED') {
    return {
      title: 'AI research is temporarily rate-limited',
      detail: 'TradeLens has reached its AI research provider usage limit for now. Please wait briefly and try again.',
    }
  }
  if (PROVIDER_UNAVAILABLE_CODES.has(error.code)) {
    return {
      title: 'AI synthesis is temporarily unavailable',
      detail: 'TradeLens could not reach its AI research provider. Please try again shortly.',
    }
  }
  return { title: 'Research request failed', detail: 'Something went wrong while researching this question. Please try again.' }
}

/** Phase 5E: the AI Research Workspace -- an explainable quantitative
 * research tool over the accepted Phase 5C research agent, NOT a
 * chatbot. One question -> one structured result: AI synthesis,
 * deterministic tool evidence, authoritative knowledge sources, and
 * persistent research-boundary copy are always rendered as visually
 * distinct sections (see CLAUDE.md Phase 5E). No conversation history,
 * no streaming. */
export default function ResearchPage() {
  const research = useResearchQuery()

  return (
    <div className="space-y-6">
      <PageHeader
        title="Research Workspace"
        description="Ask TradeLens to investigate its deterministic strategy evidence and documented methodology. Every answer is grounded in TradeLens's own accepted tools and knowledge base -- never a general-purpose chatbot."
      />

      <ResearchQuestionForm onSubmit={research.run} loading={research.loading} />

      {!research.data && !research.loading && !research.error && (
        <NothingSelectedState message="No result yet. Ask a research question above, or pick a suggested question." />
      )}

      {research.loading && (
        <Card className="p-6">
          <p className="mb-3 text-sm text-[var(--text-secondary)]">Researching deterministic TradeLens evidence...</p>
          <LoadingSkeleton lines={5} />
        </Card>
      )}

      {!research.loading && research.error && (
        <Card className="p-6">
          {(() => {
            const { title, detail } = researchErrorMessage(research.error)
            return (
              <div role="alert">
                <p className="text-sm font-medium text-[var(--negative)]">{title}</p>
                <p className="mt-1 text-sm text-[var(--text-secondary)]">{detail}</p>
              </div>
            )
          })()}
        </Card>
      )}

      {!research.loading && !research.error && research.data && (
        <div className="space-y-4">
          <ResearchSynthesis question={research.data.question} answer={research.data.answer} stoppedReason={research.data.stopped_reason} />

          <Card className="p-4">
            <SectionLabel>Deterministic Evidence / Tools Used</SectionLabel>
            <div className="mt-2">
              <ToolTraceList trace={research.data.tool_trace} />
            </div>
          </Card>

          <Card className="p-4">
            <SectionLabel>Knowledge Sources</SectionLabel>
            <div className="mt-2">
              <KnowledgeSourcesList sources={research.data.knowledge_sources} />
            </div>
          </Card>
        </div>
      )}

      <ResearchBoundaries />
    </div>
  )
}
