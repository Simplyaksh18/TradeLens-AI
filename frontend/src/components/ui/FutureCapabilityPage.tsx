import type { LucideIcon } from 'lucide-react'

interface FutureCapabilityPageProps {
  eyebrow: string
  title: string
  phase: string
  summary: string
  pipelinePosition: string
  icon: LucideIcon
}

export function FutureCapabilityPage({ eyebrow, title, phase, summary, pipelinePosition, icon: Icon }: FutureCapabilityPageProps) {
  return (
    <div className="space-y-6">
      <div className="rounded-lg border border-[var(--border)] bg-[var(--surface-1)] p-8">
        <div className="flex items-start gap-4">
          <div className="rounded-md border border-[var(--border)] bg-[var(--surface-2)] p-3">
            <Icon size={22} className="text-[var(--accent)]" aria-hidden="true" />
          </div>
          <div className="space-y-3">
            <div>
              <div className="text-[11px] font-semibold uppercase tracking-wider text-[var(--text-tertiary)]">{eyebrow}</div>
              <h1 className="mt-1 text-xl font-semibold text-[var(--text-primary)]">{title}</h1>
            </div>
            <p className="max-w-2xl text-sm leading-relaxed text-[var(--text-secondary)]">{summary}</p>
            <p className="text-xs text-[var(--text-tertiary)]">
              Pipeline position: <span className="font-mono-tabular text-[var(--text-secondary)]">{pipelinePosition}</span>
            </p>
            <span className="inline-flex items-center rounded border border-[var(--accent)]/30 bg-[var(--accent-soft)] px-2.5 py-1 text-xs font-medium text-[var(--accent-strong)]">
              Planned for {phase}
            </span>
          </div>
        </div>
      </div>
    </div>
  )
}
