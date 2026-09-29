import { useState } from 'react'
import { InstrumentSearch } from './InstrumentSearch'
import { DateRangeSelector } from './DateRangeSelector'
import { computeRangeForShortcut } from '../../utils/dateRange'
import type { Instrument } from '../../api/types'

export interface InvestigationSelection {
  instrument: Instrument
  start: string
  end: string
  interval: '1d'
}

interface InvestigationControlsProps {
  onRun: (selection: InvestigationSelection) => void
}

/** Controls for the Phase 4F Strategy Failure Investigator. Only
 * "Trend + Momentum v1" exists (fixed/read-only) and interval is fixed at
 * 1D (the only supported interval) -- neither is presented as a real
 * choice, matching the existing Strategy Auditor/Backtests convention.
 * `start`/`end` define the historical BUY-signal INVESTIGATION POPULATION
 * (both inclusive) -- client-side validation here is UX only; the backend
 * remains authoritative (see CLAUDE.md Phase 4E). */
export function InvestigationControls({ onRun }: InvestigationControlsProps) {
  const [instrument, setInstrument] = useState<Instrument | null>(null)
  const [{ start, end }, setRange] = useState(() => computeRangeForShortcut('1Y'))
  const [error, setError] = useState<string | null>(null)

  function handleRun() {
    if (!instrument) {
      setError('Select an instrument first.')
      return
    }
    if (!start || !end) {
      setError('Start and end dates are required.')
      return
    }
    if (start > end) {
      setError('Start date must be on or before the end date.')
      return
    }
    setError(null)
    onRun({ instrument, start, end, interval: '1d' })
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

        <DateRangeSelector start={start} end={end} onChange={setRange} />

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
          Run Investigation
        </button>

        {instrument && (
          <span className="text-xs text-[var(--text-tertiary)]">
            Selected: <span className="font-mono-tabular text-[var(--text-secondary)]">{instrument.symbol}</span>
          </span>
        )}
      </div>

      <p className="mt-3 text-xs text-[var(--text-tertiary)]">
        The selected dates define the historical signal population. Signals near the end of the window may have
        unavailable 10-bar outcomes when insufficient forward trading bars remain -- this is expected censoring, not
        an error.
      </p>

      {error && (
        <p role="alert" className="mt-2 text-sm text-[var(--negative)]">
          {error}
        </p>
      )}
    </div>
  )
}
