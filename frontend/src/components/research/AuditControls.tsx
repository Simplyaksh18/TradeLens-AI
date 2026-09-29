import { useState } from 'react'
import { InstrumentSearch } from './InstrumentSearch'
import { computeRangeForShortcut } from '../../utils/dateRange'
import type { Instrument } from '../../api/types'

export interface AuditSelection {
  instrument: Instrument
  auditDate: string
  evidenceStart: string
  end: string
  interval: '1d'
}

interface AuditControlsProps {
  onRun: (selection: AuditSelection) => void
}

/** Controls for the Phase 3E Strategy Auditor. Only "Trend + Momentum v1"
 * is offered (no other strategy exists yet) and interval is fixed at 1D
 * (the only supported interval) — neither is presented as a real choice.
 * "Audit Date" (the point in time being inspected) and "Evidence Start"
 * (the lower bound of the historical prior-signal population) are kept as
 * two clearly distinct controls — never merged into one "start date" field,
 * since conflating them was the exact Phase 3D defect this page must not
 * reintroduce in its UI. Client-side validation here is UX only; the
 * backend remains authoritative (see CLAUDE.md Phase 3D). */
export function AuditControls({ onRun }: AuditControlsProps) {
  const [instrument, setInstrument] = useState<Instrument | null>(null)
  const defaultRange = computeRangeForShortcut('1Y')
  const [evidenceStart, setEvidenceStart] = useState(defaultRange.start)
  const [end, setEnd] = useState(defaultRange.end)
  const [auditDate, setAuditDate] = useState(defaultRange.end)
  const [error, setError] = useState<string | null>(null)

  function handleRun() {
    if (!instrument) {
      setError('Select an instrument first.')
      return
    }
    if (!evidenceStart || !end || !auditDate) {
      setError('Evidence start, data end, and audit date are all required.')
      return
    }
    if (evidenceStart > end) {
      setError('Evidence start must be on or before the data end date.')
      return
    }
    if (auditDate > end) {
      setError('Audit date must be on or before the data end date.')
      return
    }
    setError(null)
    onRun({ instrument, auditDate, evidenceStart, end, interval: '1d' })
  }

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--surface-1)] p-4">
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-xs text-[var(--text-tertiary)]">Symbol</span>
          <InstrumentSearch onSelect={setInstrument} />
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-xs text-[var(--text-tertiary)]">Strategy</span>
          <span className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)]">
            Trend + Momentum v1
          </span>
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="audit-date" className="text-xs text-[var(--text-tertiary)]">
            Audit Date
          </label>
          <input
            id="audit-date"
            type="date"
            value={auditDate}
            max={end}
            onChange={(e) => setAuditDate(e.target.value)}
            className="rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-2 py-1.5 text-sm font-mono-tabular"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="evidence-start" className="text-xs text-[var(--text-tertiary)]">
            Evidence Start
          </label>
          <input
            id="evidence-start"
            type="date"
            value={evidenceStart}
            max={end}
            onChange={(e) => setEvidenceStart(e.target.value)}
            className="rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-2 py-1.5 text-sm font-mono-tabular"
          />
        </div>

        <div className="flex flex-col gap-1">
          <label htmlFor="data-end" className="text-xs text-[var(--text-tertiary)]">
            Data End
          </label>
          <input
            id="data-end"
            type="date"
            value={end}
            min={evidenceStart}
            onChange={(e) => setEnd(e.target.value)}
            className="rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-2 py-1.5 text-sm font-mono-tabular"
          />
        </div>

        <div className="flex flex-col gap-1">
          <span className="text-xs text-[var(--text-tertiary)]">Interval</span>
          <span className="rounded border border-[var(--border)] bg-[var(--surface-2)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)]">
            1D
          </span>
        </div>

        <button
          type="button"
          onClick={handleRun}
          className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-all hover:bg-[var(--accent-strong)] active:scale-[0.98]"
        >
          Run Audit
        </button>

        {instrument && (
          <span className="text-xs text-[var(--text-tertiary)]">
            Selected: <span className="font-mono-tabular text-[var(--text-secondary)]">{instrument.symbol}</span>
          </span>
        )}
      </div>

      <p className="mt-3 text-xs text-[var(--text-tertiary)]">
        Evidence Start sets which prior strategy signals are included in the historical evidence below. Indicator
        warm-up (SMA/RSI/volatility) is handled separately and does not depend on this date.
      </p>

      {error && (
        <p role="alert" className="mt-2 text-sm text-[var(--negative)]">
          {error}
        </p>
      )}
    </div>
  )
}
