import { useId, useState } from 'react'
import { Search } from 'lucide-react'
import { useInstrumentSearch } from '../../hooks/useInstrumentSearch'
import type { Instrument } from '../../api/types'

interface InstrumentSearchProps {
  onSelect: (instrument: Instrument) => void
  placeholder?: string
}

export function InstrumentSearch({ onSelect, placeholder = 'Search symbol or company name…' }: InstrumentSearchProps) {
  const [query, setQuery] = useState('')
  const [open, setOpen] = useState(false)
  const { results, loading, error } = useInstrumentSearch(query)
  const listboxId = useId()

  return (
    <div className="relative w-full max-w-sm">
      <label htmlFor="instrument-search-input" className="sr-only">
        Search NSE instruments
      </label>
      <div className="flex items-center gap-2 rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-3 py-2 focus-within:border-[var(--accent)]">
        <Search size={16} className="text-[var(--text-tertiary)]" aria-hidden="true" />
        <input
          id="instrument-search-input"
          type="text"
          role="combobox"
          aria-expanded={open}
          aria-controls={listboxId}
          autoComplete="off"
          className="w-full bg-transparent text-sm outline-none placeholder:text-[var(--text-tertiary)]"
          placeholder={placeholder}
          value={query}
          onChange={(e) => {
            setQuery(e.target.value)
            setOpen(true)
          }}
          onFocus={() => setOpen(true)}
          onBlur={() => window.setTimeout(() => setOpen(false), 150)}
        />
      </div>

      {open && query.trim().length > 0 && (
        <ul
          id={listboxId}
          role="listbox"
          className="absolute z-20 mt-1 max-h-72 w-full overflow-auto rounded-md border border-[var(--border)] bg-[var(--surface-raised)] shadow-[var(--shadow-2)]"
        >
          {loading && <li className="px-3 py-2 text-sm text-[var(--text-tertiary)]">Searching…</li>}
          {error && <li className="px-3 py-2 text-sm text-[var(--negative)]">{error.message}</li>}
          {!loading && !error && results.length === 0 && (
            <li className="px-3 py-2 text-sm text-[var(--text-tertiary)]">No matching instruments.</li>
          )}
          {results.map((instrument) => (
            <li key={instrument.symbol} role="option" aria-selected="false">
              <button
                type="button"
                className="flex w-full flex-col items-start gap-0.5 px-3 py-2 text-left text-sm hover:bg-[var(--surface-2)]"
                onMouseDown={(e) => e.preventDefault()}
                onClick={() => {
                  onSelect(instrument)
                  setQuery(instrument.symbol)
                  setOpen(false)
                }}
              >
                <span className="font-medium font-mono-tabular">{instrument.symbol}</span>
                <span className="text-xs text-[var(--text-tertiary)]">{instrument.name}</span>
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
