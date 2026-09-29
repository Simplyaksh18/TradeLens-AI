import type { AuditToolEvidence, ToolTraceEntry } from '../../api/types'
import { AuditEvidenceBoundary } from './AuditEvidenceBoundary'
import { ToolEvidenceSummary } from './ToolEvidenceSummary'

const STATUS_LABEL: Record<ToolTraceEntry['status'], string> = {
  ok: 'Completed',
  error: 'Failed',
  rejected: 'Rejected',
}

const STATUS_STYLE: Record<ToolTraceEntry['status'], string> = {
  ok: 'text-[var(--positive)]',
  error: 'text-[var(--negative)]',
  rejected: 'text-[var(--text-tertiary)]',
}

function ToolTraceCard({ entry }: { entry: ToolTraceEntry }) {
  return (
    <div className="rounded-md border border-[var(--border)] p-3">
      <div className="flex items-center justify-between gap-2">
        <span className="font-mono-tabular text-sm font-medium text-[var(--text-primary)]">{entry.tool_name}</span>
        <span className={`text-xs font-medium ${STATUS_STYLE[entry.status]}`}>{STATUS_LABEL[entry.status]}</span>
      </div>

      {entry.status === 'ok' ? (
        <div className="mt-2">
          <ToolEvidenceSummary entry={entry} />
        </div>
      ) : (
        <p className="mt-2 text-xs text-[var(--text-secondary)]">{entry.result_summary}</p>
      )}

      {entry.tool_name === 'audit_strategy_decision' && entry.raw_result && (
        <div className="mt-3">
          <AuditEvidenceBoundary evidence={entry.raw_result as unknown as AuditToolEvidence} />
        </div>
      )}
    </div>
  )
}

/** Section B: deterministic evidence / tools used. Renders `tool_trace`
 * as compact, human-readable evidence cards -- no raw backend JSON is
 * shown in this user-facing view, and there is no "View structured tool
 * details" debug dump (see CLAUDE.md Phase 5E UI polish; `raw_result`
 * itself is unchanged in the API contract, only its default frontend
 * presentation was replaced). Never labeled "AI reasoning" -- there is no
 * chain-of-thought here to expose (see app.agent.models.ToolTraceEntry). */
export function ToolTraceList({ trace }: { trace: ToolTraceEntry[] }) {
  if (trace.length === 0) {
    return <p className="text-sm text-[var(--text-tertiary)]">No tools were used to answer this question.</p>
  }
  return (
    <div className="space-y-2">
      {trace.map((entry, index) => (
        <ToolTraceCard key={`${entry.tool_name}-${index}`} entry={entry} />
      ))}
    </div>
  )
}
