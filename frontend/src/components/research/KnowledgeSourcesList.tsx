import { useState } from 'react'
import { BookMarked, ChevronDown, ChevronUp } from 'lucide-react'
import type { KnowledgeSource } from '../../api/types'

interface GroupedSource {
  documentId: string
  documentTitle: string
  chunks: KnowledgeSource[]
  sectionHeadings: string[]
}

/** Groups retrieved chunks belonging to the same source document into one
 * entry -- e.g. 3 chunks from `strategy_trend_momentum_v1` become ONE
 * source card with 3 supporting excerpts, not 3 separate cards. Order
 * preserved: first group appears in the order its first chunk was
 * retrieved; chunks within a group keep their retrieval order. No chunk
 * is dropped -- every one is still reachable in the expandable detail. */
function groupByDocument(sources: KnowledgeSource[]): GroupedSource[] {
  const groups: GroupedSource[] = []
  const byDocumentId = new Map<string, GroupedSource>()

  for (const source of sources) {
    let group = byDocumentId.get(source.document_id)
    if (!group) {
      group = { documentId: source.document_id, documentTitle: source.document_title, chunks: [], sectionHeadings: [] }
      byDocumentId.set(source.document_id, group)
      groups.push(group)
    }
    group.chunks.push(source)
    if (source.section_heading && !group.sectionHeadings.includes(source.section_heading)) {
      group.sectionHeadings.push(source.section_heading)
    }
  }

  return groups
}

function SourceCard({ group, index }: { group: GroupedSource; index: number }) {
  const [expanded, setExpanded] = useState(false)
  const excerptCount = group.chunks.length

  return (
    <li className="rounded-md border border-[var(--border)] p-3">
      <div className="flex items-start gap-2">
        <BookMarked size={14} className="mt-0.5 shrink-0 text-[var(--accent)]" aria-hidden="true" />
        <div className="min-w-0 flex-1">
          <p className="text-sm font-medium text-[var(--text-primary)]">
            <span className="text-[var(--text-tertiary)]">[{index + 1}]</span> {group.documentTitle}
          </p>
          {group.sectionHeadings.length > 0 && (
            <p className="text-xs text-[var(--text-secondary)]">{group.sectionHeadings.join(' · ')}</p>
          )}
          <p className="mt-1 text-[11px] text-[var(--text-tertiary)]">
            {excerptCount} supporting {excerptCount === 1 ? 'excerpt' : 'excerpts'}
          </p>

          <button
            type="button"
            onClick={() => setExpanded((v) => !v)}
            className="mt-1.5 inline-flex items-center gap-1 text-xs text-[var(--accent)] hover:underline"
            aria-expanded={expanded}
          >
            {expanded ? <ChevronUp size={12} aria-hidden="true" /> : <ChevronDown size={12} aria-hidden="true" />}
            View details
          </button>

          {expanded && (
            <dl className="mt-2 space-y-1.5 border-t border-[var(--border)] pt-2">
              {group.chunks.map((chunk) => (
                <div key={chunk.chunk_id} className="text-[11px]">
                  <div className="flex flex-wrap items-center gap-2 text-[var(--text-tertiary)]">
                    {chunk.section_heading && <span className="text-[var(--text-secondary)]">{chunk.section_heading}</span>}
                    <span className="rounded border border-[var(--border)] px-1.5 py-0.5 font-mono-tabular">{chunk.trust}</span>
                    <span className="font-mono-tabular">{chunk.chunk_id}</span>
                  </div>
                </div>
              ))}
            </dl>
          )}
        </div>
      </div>
    </li>
  )
}

/** Section C: deterministic Phase 5A provenance. Only actual retrieved
 * `search_research_knowledge` results reach this list (see
 * app.agent.agent.run_research_agent -- knowledge_sources is
 * reconstructed from real tool results, never parsed from generated
 * text), so a model-fabricated citation marker can never appear here.
 * Presented as SOURCES (grouped by document), not raw internal RAG chunk
 * objects -- provenance/trust/chunk IDs remain fully accessible in the
 * per-source "View details" expansion, never removed, never dominant in
 * the default collapsed view. */
export function KnowledgeSourcesList({ sources }: { sources: KnowledgeSource[] }) {
  if (sources.length === 0) {
    return <p className="text-sm text-[var(--text-tertiary)]">No knowledge-base sources were used for this answer.</p>
  }

  const groups = groupByDocument(sources)
  const documentLabel = groups.length === 1 ? 'source document' : 'source documents'
  const excerptLabel = sources.length === 1 ? 'supporting excerpt' : 'supporting excerpts'

  return (
    <div>
      <p className="mb-2 text-xs text-[var(--text-tertiary)]">
        {groups.length} {documentLabel} &middot; {sources.length} {excerptLabel}
      </p>
      <ul className="space-y-2">
        {groups.map((group, index) => (
          <SourceCard key={group.documentId} group={group} index={index} />
        ))}
      </ul>
    </div>
  )
}
