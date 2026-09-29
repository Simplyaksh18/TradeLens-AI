import { useState } from 'react'
import { InstrumentSearch } from './InstrumentSearch'
import { DateRangeSelector } from './DateRangeSelector'
import { computeRangeForShortcut } from '../../utils/dateRange'
import type { Instrument } from '../../api/types'

export interface ResearchSelection {
  instrument: Instrument
  start: string
  end: string
  interval: '1d'
}

interface ResearchToolbarProps {
  onLoad: (selection: ResearchSelection) => void
  initialInstrument?: Instrument | null
}

export function ResearchToolbar({ onLoad, initialInstrument = null }: ResearchToolbarProps) {
  const [instrument, setInstrument] = useState<Instrument | null>(initialInstrument)
  const [{ start, end }, setRange] = useState(() => computeRangeForShortcut('1Y'))

  return (
    <div className="flex flex-wrap items-end gap-4 rounded-md border border-[var(--border)] bg-[var(--surface-1)] p-4">
      <div className="flex flex-col gap-1">
        <span className="text-xs text-[var(--text-tertiary)]">Symbol</span>
        <InstrumentSearch onSelect={setInstrument} />
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
        disabled={!instrument}
        onClick={() => instrument && onLoad({ instrument, start, end, interval: '1d' })}
        className="rounded-md bg-[var(--accent)] px-4 py-2 text-sm font-medium text-white transition-all hover:bg-[var(--accent-strong)] active:scale-[0.98] disabled:cursor-not-allowed disabled:opacity-40 disabled:active:scale-100"
      >
        Load Data
      </button>

      {instrument && (
        <span className="text-xs text-[var(--text-tertiary)]">
          Selected: <span className="font-mono-tabular text-[var(--text-secondary)]">{instrument.symbol}</span>
        </span>
      )}
    </div>
  )
}
