import type { ToolTraceEntry } from '../../api/types'
import { formatDate, formatInteger, formatPercent } from '../../utils/format'

function EvidenceRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex justify-between gap-3 py-0.5 text-xs">
      <span className="text-[var(--text-tertiary)]">{label}</span>
      <span className="font-mono-tabular text-[var(--text-secondary)]">{value}</span>
    </div>
  )
}

function periodLabel(args: Record<string, unknown>): string | null {
  const { start, end } = args
  if (typeof start !== 'string' || typeof end !== 'string') return null
  return `${formatDate(start)} – ${formatDate(end)}`
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return value && typeof value === 'object' ? (value as Record<string, unknown>) : null
}

/** Human-readable, per-tool evidence card -- replaces raw backend JSON in
 * the user-facing Research Workspace (see CLAUDE.md Phase 5E UI polish).
 * Every value is read verbatim from `entry.raw_result`/`entry.arguments`
 * (the accepted, unchanged Phase 5C tool output); nothing here recomputes
 * a financial value -- only presentation formatting via the existing
 * `utils/format.ts` helpers. Returns `null` when there is no successful
 * structured result to summarize (error/rejected steps, or a tool name
 * this component doesn't have a dedicated layout for). */
export function ToolEvidenceSummary({ entry }: { entry: ToolTraceEntry }) {
  const { tool_name, arguments: args, raw_result } = entry
  if (!raw_result) return null
  const period = periodLabel(args)

  switch (tool_name) {
    case 'search_instruments': {
      const results = Array.isArray(raw_result.results) ? raw_result.results.map(asRecord).filter((r): r is Record<string, unknown> => r !== null) : []
      const first = results[0]
      return (
        <div>
          <p className="text-xs font-semibold text-[var(--text-primary)]">Instrument Resolution</p>
          <EvidenceRow label="Query" value={String(args.query ?? '—')} />
          <EvidenceRow label="Resolved" value={first ? String(first.name) : 'No matching instrument found'} />
          {first && <EvidenceRow label="Symbol" value={String(first.symbol)} />}
        </div>
      )
    }

    case 'get_strategy_evaluation':
      return (
        <div>
          <p className="text-xs font-semibold text-[var(--text-primary)]">Strategy Evaluation</p>
          <EvidenceRow label="Symbol" value={String(raw_result.symbol)} />
          <EvidenceRow label="Target Date" value={formatDate(String(raw_result.target_date))} />
          <EvidenceRow label="Decision" value={String(raw_result.decision)} />
        </div>
      )

    case 'get_signal_outcomes':
      return (
        <div>
          <p className="text-xs font-semibold text-[var(--text-primary)]">Signal Outcomes</p>
          <EvidenceRow label="Symbol" value={String(raw_result.symbol)} />
          {period && <EvidenceRow label="Period" value={period} />}
          <EvidenceRow label="Signals Found" value={formatInteger(Number(raw_result.count))} />
        </div>
      )

    case 'run_backtest':
      return (
        <div>
          <p className="text-xs font-semibold text-[var(--text-primary)]">Backtest Execution</p>
          <EvidenceRow label="Symbol" value={String(raw_result.symbol)} />
          {period && <EvidenceRow label="Period" value={period} />}
          <EvidenceRow label="Closed Trades" value={formatInteger(Number(raw_result.closed_trade_count))} />
          <EvidenceRow label="Open Position" value={raw_result.open_position ? 'Yes' : 'No'} />
        </div>
      )

    case 'get_performance_analytics':
      return (
        <div>
          <p className="text-xs font-semibold text-[var(--text-primary)]">Performance Analytics</p>
          <EvidenceRow label="Symbol" value={String(raw_result.symbol)} />
          {period && <EvidenceRow label="Period" value={period} />}
          <EvidenceRow label="Closed Trades" value={formatInteger(Number(raw_result.closed_trade_count))} />
          <EvidenceRow label="Total Return" value={formatPercent(raw_result.total_return as number | null, { signed: true })} />
          <EvidenceRow label="Maximum Drawdown" value={formatPercent(raw_result.maximum_drawdown as number | null, { signed: true })} />
          {/* Exposure = fraction of evaluated bars/time the strategy held a position -- never capital allocation. See CLAUDE.md Phase 5E UI polish. */}
          <EvidenceRow label="Exposure (time in position)" value={formatPercent(raw_result.exposure as number | null)} />
        </div>
      )

    case 'audit_strategy_decision':
      // The dedicated Decision Evidence / Point-in-Time Context /
      // Retrospective-Hindsight blocks (AuditEvidenceBoundary) render
      // separately, below this summary header -- see ToolTraceList.
      return (
        <div>
          <p className="text-xs font-semibold text-[var(--text-primary)]">Strategy Audit</p>
          <EvidenceRow label="Symbol" value={String(raw_result.symbol)} />
          <EvidenceRow label="Audit Date" value={formatDate(String(raw_result.audit_date))} />
          <EvidenceRow label="Decision" value={String(raw_result.decision)} />
        </div>
      )

    case 'investigate_strategy_failures':
      return (
        <div>
          <p className="text-xs font-semibold text-[var(--text-primary)]">Failure Investigation</p>
          <EvidenceRow label="Symbol" value={String(raw_result.symbol)} />
          {period && <EvidenceRow label="Period" value={period} />}
          <EvidenceRow label="Total Signals" value={formatInteger(Number(raw_result.total_signal_count))} />
          <EvidenceRow label="Eligible" value={formatInteger(Number(raw_result.eligible_count))} />
          <EvidenceRow label="Failed" value={formatInteger(Number(raw_result.failed_count))} />
          <EvidenceRow label="Non-Failed" value={formatInteger(Number(raw_result.non_failed_count))} />
          <EvidenceRow label="Unavailable" value={formatInteger(Number(raw_result.unavailable_count))} />
        </div>
      )

    case 'search_research_knowledge': {
      const results = Array.isArray(raw_result.results) ? raw_result.results : []
      return (
        <div>
          <p className="text-xs font-semibold text-[var(--text-primary)]">Research Knowledge</p>
          <EvidenceRow label="Query" value={String(args.query ?? '—')} />
          <EvidenceRow label="Sources Retrieved" value={formatInteger(results.length)} />
        </div>
      )
    }

    default:
      return null
  }
}
