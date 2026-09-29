import { useEffect, useRef, useState } from 'react'
import { createChart, LineSeries, type IChartApi, type ISeriesApi, type MouseEventParams, type Time, type UTCTimestamp } from 'lightweight-charts'
import { useTheme } from '../../theme/useTheme'
import { formatDate } from '../../utils/format'

export interface LineChartPoint {
  date: string
  value: number
}

interface SimpleLineChartProps {
  data: LineChartPoint[]
  height?: number
  valueLabel: string
  formatValue: (value: number) => string
  color?: 'accent' | 'negative'
  emptyMessage?: string
  testId?: string
}

function toTimestamp(isoDate: string): UTCTimestamp {
  return (Date.parse(`${isoDate}T00:00:00Z`) / 1000) as UTCTimestamp
}

function readColors(colorKey: 'accent' | 'negative') {
  const styles = getComputedStyle(document.documentElement)
  const read = (name: string) => styles.getPropertyValue(name).trim()
  return {
    text: read('--text-secondary'),
    grid: read('--chart-grid'),
    border: read('--border'),
    line: read(colorKey === 'negative' ? '--negative' : '--accent'),
  }
}

/** A single-series line chart shared by the equity curve and drawdown
 * views (Phase 2E). Create-once + restyle-in-place on theme change — same
 * architecture as PriceChart/RsiChart, which fixed a real bug where
 * recreating the chart on every theme toggle silently dropped series data
 * (see CLAUDE.md Phase 1H). Renders exactly the values it's given; never
 * recomputes equity/drawdown. */
export function SimpleLineChart({
  data,
  height = 220,
  valueLabel,
  formatValue,
  color = 'accent',
  emptyMessage = 'No data for the selected period.',
  testId = 'simple-line-chart',
}: SimpleLineChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const { preference: resolved } = useTheme()
  const [hover, setHover] = useState<LineChartPoint | null>(null)
  const byDate = useRef(new Map<string, number>())
  byDate.current = new Map(data.map((d) => [d.date, d.value]))

  useEffect(() => {
    if (!containerRef.current) return
    const colors = readColors(color)

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: { background: { color: 'transparent' }, textColor: colors.text },
      grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
      rightPriceScale: { borderColor: colors.border },
      timeScale: { borderColor: colors.border },
    })
    chartRef.current = chart
    seriesRef.current = chart.addSeries(LineSeries, { color: colors.line, lineWidth: 2 })

    const handleCrosshairMove = (param: MouseEventParams<Time>) => {
      if (!param.time) {
        setHover(null)
        return
      }
      const date = new Date(Number(param.time) * 1000).toISOString().slice(0, 10)
      const value = byDate.current.get(date)
      setHover(value === undefined ? null : { date, value })
    }
    chart.subscribeCrosshairMove(handleCrosshairMove)

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove)
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !seriesRef.current) return
    const colors = readColors(color)
    chart.applyOptions({
      layout: { textColor: colors.text },
      grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
      rightPriceScale: { borderColor: colors.border },
      timeScale: { borderColor: colors.border },
    })
    seriesRef.current.applyOptions({ color: colors.line })
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolved, color])

  useEffect(() => {
    if (!seriesRef.current) return
    seriesRef.current.setData(data.map((d) => ({ time: toTimestamp(d.date), value: d.value })))
    chartRef.current?.timeScale().fitContent()
  }, [data])

  const latest = data.at(-1) ?? null
  const displayed = hover ?? latest

  if (data.length === 0) {
    return (
      <div className="flex h-[120px] items-center justify-center rounded-md border border-[var(--border)] text-sm text-[var(--text-tertiary)]">
        {emptyMessage}
      </div>
    )
  }

  return (
    <div className="w-full">
      <div
        className="mb-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-xs"
        data-testid={`${testId}-legend`}
      >
        {displayed ? (
          <>
            <span className="font-medium text-[var(--text-primary)]">{formatDate(displayed.date)}</span>
            <span className="whitespace-nowrap">
              <span className="text-[var(--text-tertiary)]">{valueLabel} </span>
              <span className="font-mono-tabular text-[var(--text-primary)]">{formatValue(displayed.value)}</span>
            </span>
          </>
        ) : (
          <span className="text-[var(--text-tertiary)]">No data loaded.</span>
        )}
      </div>
      <div style={{ height }} ref={containerRef} data-testid={testId} />
    </div>
  )
}
