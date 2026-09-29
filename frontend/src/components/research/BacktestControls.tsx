import { useState } from 'react'
import { InstrumentSearch } from './InstrumentSearch'
import { DateRangeSelector } from './DateRangeSelector'
import { computeRangeForShortcut } from '../../utils/dateRange'
import type { Instrument } from '../../api/types'

export interface BacktestSelection {
  instrument: Instrument
  start: string
  end: string
  initialCapital: number
  interval: '1d'
}

interface BacktestControlsProps {
  onRun: (selection: BacktestSelection) => void
}

const DEFAULT_CAPITAL = 100_000

/** Research controls for the Phase 2E backtest workspace. Only what's
 * actually configurable in the accepted Phase 2B/2C V1 contract is exposed
 * here — no transaction cost, slippage, leverage, shorting, or position
 * sizing controls (none of those exist in V1). Validation here is UX only;
 * the backend remains authoritative (see CLAUDE.md Phase 2B/2D). */
export function BacktestControls({ onRun }: BacktestControlsProps) {
  const [instrument, setInstrument] = useState<Instrument | null>(null)
  const [{ start, end }, setRange] = useState(() => computeRangeForShortcut('1Y'))
  const [capitalInput, setCapitalInput] = useState(String(DEFAULT_CAPITAL))
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
    const initialCapital = Number(capitalInput)
    if (!Number.isFinite(initialCapital) || initialCapital <= 0) {
      setError('Initial capital must be a positive number.')
      return
    }
    setError(null)
    onRun({ instrument, start, end, initialCapital, interval: '1d' })
  }

  return (
    <div className="rounded-md border border-[var(--border)] bg-[var(--surface-1)] p-4">
      <div className="flex flex-wrap items-end gap-4">
        <div className="flex flex-col gap-1">
          <span className="text-xs text-[var(--text-tertiary)]">Symbol</span>
          <InstrumentSearch onSelect={setInstrument} />
        </div>

        <DateRangeSelector start={start} end={end} onChange={setRange} />

        <div className="flex flex-col gap-1">
          <label htmlFor="backtest-initial-capital" className="text-xs text-[var(--text-tertiary)]">
            Initial Capital (₹)
          </label>
          <input
            id="backtest-initial-capital"
            type="number"
            min={1}
            step="any"
            inputMode="decimal"
            value={capitalInput}
            onChange={(e) => setCapitalInput(e.target.value)}
            className="w-36 rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-2.5 py-1.5 text-sm font-mono-tabular outline-none focus:border-[var(--accent)]"
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
          Run Backtest
        </button>

        {instrument && (
          <span className="text-xs text-[var(--text-tertiary)]">
            Selected: <span className="font-mono-tabular text-[var(--text-secondary)]">{instrument.symbol}</span>
          </span>
        )}
      </div>

      {error && (
        <p role="alert" className="mt-3 text-sm text-[var(--negative)]">
          {error}
        </p>
      )}
    </div>
  )
}
