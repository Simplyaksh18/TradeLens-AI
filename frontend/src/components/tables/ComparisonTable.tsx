export interface ComparisonRow {
  label: string
  failed: string
  nonFailed: string
}

/** Purely presentational Failed-vs-Non-Failed metric table. Takes already-
 * formatted strings -- no computation, no derived difference/winner
 * column (see CLAUDE.md Phase 4F: comparisons are presentation only). */
export function ComparisonTable({ rows }: { rows: ComparisonRow[] }) {
  return (
    <div className="overflow-x-auto rounded-md border border-[var(--border)]">
      <table className="w-full min-w-[420px] text-sm">
        <thead>
          <tr className="border-b border-[var(--border)] bg-[var(--surface-2)] text-left text-xs uppercase tracking-wide text-[var(--text-tertiary)]">
            <th className="px-3 py-2 font-medium">Metric</th>
            <th className="px-3 py-2 font-medium text-right">Failed</th>
            <th className="px-3 py-2 font-medium text-right">Non-Failed</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row) => (
            <tr key={row.label} className="border-b border-[var(--border)] last:border-0">
              <td className="px-3 py-1.5 text-[var(--text-secondary)]">{row.label}</td>
              <td className="px-3 py-1.5 text-right font-mono-tabular text-[var(--text-primary)]">{row.failed}</td>
              <td className="px-3 py-1.5 text-right font-mono-tabular text-[var(--text-primary)]">{row.nonFailed}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}
