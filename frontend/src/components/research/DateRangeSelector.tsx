import { RANGE_SHORTCUTS, computeRangeForShortcut, type RangeShortcut } from '../../utils/dateRange'

interface DateRangeSelectorProps {
  start: string
  end: string
  onChange: (range: { start: string; end: string }) => void
}

export function DateRangeSelector({ start, end, onChange }: DateRangeSelectorProps) {
  return (
    <div className="flex flex-wrap items-end gap-3">
      <div className="flex flex-col gap-1">
        <label htmlFor="range-start" className="text-xs text-[var(--text-tertiary)]">
          Start
        </label>
        <input
          id="range-start"
          type="date"
          value={start}
          max={end}
          onChange={(e) => onChange({ start: e.target.value, end })}
          className="rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-2 py-1.5 text-sm font-mono-tabular"
        />
      </div>
      <div className="flex flex-col gap-1">
        <label htmlFor="range-end" className="text-xs text-[var(--text-tertiary)]">
          End
        </label>
        <input
          id="range-end"
          type="date"
          value={end}
          min={start}
          onChange={(e) => onChange({ start, end: e.target.value })}
          className="rounded-md border border-[var(--border)] bg-[var(--surface-1)] px-2 py-1.5 text-sm font-mono-tabular"
        />
      </div>
      <div className="flex flex-wrap gap-1" role="group" aria-label="Date range shortcuts">
        {RANGE_SHORTCUTS.map((shortcut: RangeShortcut) => (
          <button
            key={shortcut}
            type="button"
            className="rounded border border-[var(--border)] px-2.5 py-1.5 text-xs font-medium text-[var(--text-secondary)] hover:bg-[var(--surface-2)] hover:text-[var(--text-primary)]"
            onClick={() => onChange(computeRangeForShortcut(shortcut))}
          >
            {shortcut}
          </button>
        ))}
      </div>
    </div>
  )
}
