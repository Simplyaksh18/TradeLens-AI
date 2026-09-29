import { useEffect, useRef } from 'react'
import { createChart, LineSeries, type IChartApi, type ISeriesApi, type IPriceLine, type UTCTimestamp } from 'lightweight-charts'
import type { IndicatorRow } from '../../api/types'
import { useTheme } from '../../theme/useTheme'

function toTimestamp(isoDate: string): UTCTimestamp {
  return (Date.parse(`${isoDate}T00:00:00Z`) / 1000) as UTCTimestamp
}

function readColors() {
  const styles = getComputedStyle(document.documentElement)
  const read = (name: string) => styles.getPropertyValue(name).trim()
  return {
    text: read('--text-secondary'),
    grid: read('--chart-grid'),
    border: read('--border'),
    accent: read('--accent'),
    negative: read('--negative'),
    positive: read('--positive'),
  }
}

export function RsiChart({ rows, height = 140 }: { rows: IndicatorRow[]; height?: number }) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const seriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const upperLineRef = useRef<IPriceLine | null>(null)
  const lowerLineRef = useRef<IPriceLine | null>(null)
  const { preference: resolved } = useTheme()

  // Created once; restyled in place on theme change (see effect below) —
  // same fix as PriceChart: recreating on every theme toggle meant the RSI
  // line data only got reapplied when `rows` changed, so it vanished after
  // a Light/Dark switch until the next data load.
  useEffect(() => {
    if (!containerRef.current) return
    const colors = readColors()

    const chart = createChart(containerRef.current, {
      autoSize: true,
      layout: { background: { color: 'transparent' }, textColor: colors.text },
      grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
      rightPriceScale: { borderColor: colors.border },
      timeScale: { borderColor: colors.border },
    })
    chartRef.current = chart

    const series = chart.addSeries(LineSeries, { color: colors.accent, lineWidth: 2, lastValueVisible: true })
    seriesRef.current = series
    upperLineRef.current = series.createPriceLine({ price: 70, color: colors.negative, lineWidth: 1, lineStyle: 2, title: '70' })
    lowerLineRef.current = series.createPriceLine({ price: 40, color: colors.positive, lineWidth: 1, lineStyle: 2, title: '40' })

    return () => {
      chart.remove()
      chartRef.current = null
      seriesRef.current = null
      upperLineRef.current = null
      lowerLineRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !seriesRef.current) return
    const colors = readColors()
    chart.applyOptions({
      layout: { textColor: colors.text },
      grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
      rightPriceScale: { borderColor: colors.border },
      timeScale: { borderColor: colors.border },
    })
    seriesRef.current.applyOptions({ color: colors.accent })
    upperLineRef.current?.applyOptions({ color: colors.negative })
    lowerLineRef.current?.applyOptions({ color: colors.positive })
  }, [resolved])

  useEffect(() => {
    if (!seriesRef.current) return
    seriesRef.current.setData(
      rows.filter((r) => r.rsi14 !== null).map((r) => ({ time: toTimestamp(r.date), value: r.rsi14 as number })),
    )
    chartRef.current?.timeScale().fitContent()
  }, [rows])

  return <div className="w-full" style={{ height }} ref={containerRef} data-testid="rsi-chart" />
}
