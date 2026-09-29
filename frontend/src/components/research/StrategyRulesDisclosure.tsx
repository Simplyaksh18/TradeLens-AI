import type { StrategyMetadata } from '../../utils/strategyMetadata'

/** Compact, collapsible "About this strategy" disclosure shown near the
 * Strategy control. Purely explanatory/static metadata -- these rules are
 * never (re)calculated here; the actual decision always comes from the
 * Phase 3D API response (see EvidenceInspector). Uses a native
 * <details>/<summary> element since no dedicated disclosure component
 * exists yet in components/ui -- avoids introducing one for a single use. */
export function StrategyRulesDisclosure({ metadata }: { metadata: StrategyMetadata }) {
  return (
    <details className="group rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-4 py-2 text-sm">
      <summary className="cursor-pointer select-none text-xs font-medium text-[var(--text-secondary)] hover:text-[var(--text-primary)]">
        About {metadata.strategyName} (Strategy Rules)
      </summary>

      <div className="mt-3 space-y-3 pb-1">
        <p className="text-sm text-[var(--text-secondary)]">{metadata.summary}</p>

        <div className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3 font-mono-tabular text-xs leading-relaxed text-[var(--text-primary)]">
          <div>BUY iff</div>
          {metadata.conditions.map((condition, i) => (
            <div key={condition}>{i === 0 ? condition : `AND ${condition}`}</div>
          ))}
        </div>

        <ul className="list-disc space-y-1 pl-4 text-xs text-[var(--text-tertiary)]">
          {metadata.semantics.map((point) => (
            <li key={point}>{point}</li>
          ))}
        </ul>
      </div>
    </details>
  )
}
