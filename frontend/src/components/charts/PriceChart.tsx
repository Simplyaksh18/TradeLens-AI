import { useEffect, useRef, useState } from 'react'
import {
  createChart,
  createSeriesMarkers,
  CandlestickSeries,
  LineSeries,
  HistogramSeries,
  type IChartApi,
  type ISeriesApi,
  type ISeriesMarkersPluginApi,
  type MouseEventParams,
  type Time,
  type UTCTimestamp,
} from 'lightweight-charts'
import type { OHLCVBar, IndicatorRow, StrategyEvaluation } from '../../api/types'
import { useTheme } from '../../theme/useTheme'
import { deriveBuyTransitionMarkers } from '../../utils/chartMarkers'
import { formatDate, formatInteger, formatNumber } from '../../utils/format'

interface PriceChartProps {
  bars: OHLCVBar[]
  indicatorRows?: IndicatorRow[]
  buySignals?: StrategyEvaluation[]
  height?: number
}

function toTimestamp(isoDate: string): UTCTimestamp {
  return (Date.parse(`${isoDate}T00:00:00Z`) / 1000) as UTCTimestamp
}

function readColors() {
  const styles = getComputedStyle(document.documentElement)
  const read = (name: string) => styles.getPropertyValue(name).trim()
  return {
    text: read('--text-secondary'),
    grid: read('--chart-grid'),
    up: read('--chart-up'),
    down: read('--chart-down'),
    sma20: read('--chart-sma20'),
    sma50: read('--chart-sma50'),
    volume: read('--chart-volume'),
    border: read('--border'),
    positive: read('--positive'),
  }
}

interface HoverInfo {
  date: string
  open: number
  high: number
  low: number
  close: number
  volume: number
  sma20: number | null
  sma50: number | null
  rsi14: number | null
}

function LegendValue({ label, value }: { label: string; value: string }) {
  return (
    <span className="whitespace-nowrap">
      <span className="text-[var(--text-tertiary)]">{label} </span>
      <span className="font-mono-tabular text-[var(--text-primary)]">{value}</span>
    </span>
  )
}

export function PriceChart({ bars, indicatorRows = [], buySignals = [], height = 420 }: PriceChartProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const chartRef = useRef<IChartApi | null>(null)
  const candleSeriesRef = useRef<ISeriesApi<'Candlestick'> | null>(null)
  const sma20SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const sma50SeriesRef = useRef<ISeriesApi<'Line'> | null>(null)
  const volumeSeriesRef = useRef<ISeriesApi<'Histogram'> | null>(null)
  const markersPluginRef = useRef<ISeriesMarkersPluginApi<Time> | null>(null)
  const { preference: resolved } = useTheme()
  const [hover, setHover] = useState<HoverInfo | null>(null)

  const barsByDate = useRef(new Map<string, OHLCVBar>())
  const indicatorsByDate = useRef(new Map<string, IndicatorRow>())
  barsByDate.current = new Map(bars.map((b) => [b.date, b]))
  indicatorsByDate.current = new Map(indicatorRows.map((r) => [r.date, r]))

  // Create the chart and series exactly once. Theme changes restyle the
  // existing chart/series in place (see the effect below) instead of
  // destroying and recreating them — recreating on every theme toggle was
  // the root cause of a real bug where SMA lines and BUY markers vanished
  // after switching Light/Dark (their own effects only re-ran when their
  // *data* changed, not when the chart/series were silently replaced).
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

    candleSeriesRef.current = chart.addSeries(CandlestickSeries, {
      upColor: colors.up,
      downColor: colors.down,
      borderVisible: false,
      wickUpColor: colors.up,
      wickDownColor: colors.down,
    })
    sma20SeriesRef.current = chart.addSeries(LineSeries, {
      color: colors.sma20,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    sma50SeriesRef.current = chart.addSeries(LineSeries, {
      color: colors.sma50,
      lineWidth: 2,
      priceLineVisible: false,
      lastValueVisible: false,
    })
    volumeSeriesRef.current = chart.addSeries(HistogramSeries, {
      color: colors.volume,
      priceFormat: { type: 'volume' },
      priceScaleId: 'volume',
    })
    volumeSeriesRef.current.priceScale().applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } })
    markersPluginRef.current = createSeriesMarkers(candleSeriesRef.current, [])

    const handleCrosshairMove = (param: MouseEventParams<Time>) => {
      if (!param.time) {
        setHover(null)
        return
      }
      const date = new Date(Number(param.time) * 1000).toISOString().slice(0, 10)
      const bar = barsByDate.current.get(date)
      if (!bar) {
        setHover(null)
        return
      }
      const indicatorRow = indicatorsByDate.current.get(date)
      setHover({
        date,
        open: bar.open,
        high: bar.high,
        low: bar.low,
        close: bar.close,
        volume: bar.volume,
        sma20: indicatorRow?.sma20 ?? null,
        sma50: indicatorRow?.sma50 ?? null,
        rsi14: indicatorRow?.rsi14 ?? null,
      })
    }
    chart.subscribeCrosshairMove(handleCrosshairMove)

    return () => {
      chart.unsubscribeCrosshairMove(handleCrosshairMove)
      chart.remove()
      chartRef.current = null
      markersPluginRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Restyle in place on theme change: colors only, no data touched, so
  // SMA/marker data set by the effects below survives a theme toggle.
  useEffect(() => {
    const chart = chartRef.current
    if (!chart || !candleSeriesRef.current || !volumeSeriesRef.current) return
    const colors = readColors()

    chart.applyOptions({
      layout: { textColor: colors.text },
      grid: { vertLines: { color: colors.grid }, horzLines: { color: colors.grid } },
      rightPriceScale: { borderColor: colors.border },
      timeScale: { borderColor: colors.border },
    })
    candleSeriesRef.current.applyOptions({
      upColor: colors.up,
      downColor: colors.down,
      wickUpColor: colors.up,
      wickDownColor: colors.down,
    })
    sma20SeriesRef.current?.applyOptions({ color: colors.sma20 })
    sma50SeriesRef.current?.applyOptions({ color: colors.sma50 })
    volumeSeriesRef.current.applyOptions({ color: colors.volume })
    volumeSeriesRef.current.setData(
      bars.map((bar) => ({
        time: toTimestamp(bar.date),
        value: bar.volume,
        color: bar.close >= bar.open ? colors.up : colors.down,
      })),
    )
    if (markersPluginRef.current) {
      markersPluginRef.current.setMarkers(
        deriveBuyTransitionMarkers(buySignals).map((marker) => ({
          time: toTimestamp(marker.date),
          position: 'belowBar' as const,
          color: colors.positive,
          shape: 'arrowUp' as const,
          text: marker.runLength > 1 ? `BUY ×${marker.runLength}` : 'BUY',
        })),
      )
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [resolved, bars, buySignals])

  // Candle OHLC data has no theme-dependent color, so this effect only
  // needs to re-run when `bars` changes (volume/marker colors are handled
  // by the restyle effect above, which also re-runs on `bars`/`buySignals`).
  useEffect(() => {
    if (!candleSeriesRef.current) return
    candleSeriesRef.current.setData(
      bars.map((bar) => ({ time: toTimestamp(bar.date), open: bar.open, high: bar.high, low: bar.low, close: bar.close })),
    )
    chartRef.current?.timeScale().fitContent()
  }, [bars])

  useEffect(() => {
    if (!sma20SeriesRef.current || !sma50SeriesRef.current) return
    sma20SeriesRef.current.setData(
      indicatorRows.filter((r) => r.sma20 !== null).map((r) => ({ time: toTimestamp(r.date), value: r.sma20 as number })),
    )
    sma50SeriesRef.current.setData(
      indicatorRows.filter((r) => r.sma50 !== null).map((r) => ({ time: toTimestamp(r.date), value: r.sma50 as number })),
    )
  }, [indicatorRows])

  const latestBar = bars.at(-1)
  const latestIndicators = latestBar ? indicatorsByDate.current.get(latestBar.date) : undefined
  const displayed: HoverInfo | null =
    hover ??
    (latestBar
      ? {
          date: latestBar.date,
          open: latestBar.open,
          high: latestBar.high,
          low: latestBar.low,
          close: latestBar.close,
          volume: latestBar.volume,
          sma20: latestIndicators?.sma20 ?? null,
          sma50: latestIndicators?.sma50 ?? null,
          rsi14: latestIndicators?.rsi14 ?? null,
        }
      : null)

  return (
    <div className="w-full">
      <div
        className="mb-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-md border border-[var(--border)] bg-[var(--surface-2)] px-3 py-1.5 text-xs"
        data-testid="chart-legend"
      >
        {displayed ? (
          <>
            <span className="font-medium text-[var(--text-primary)]">{formatDate(displayed.date)}</span>
            <LegendValue label="O" value={formatNumber(displayed.open)} />
            <LegendValue label="H" value={formatNumber(displayed.high)} />
            <LegendValue label="L" value={formatNumber(displayed.low)} />
            <LegendValue label="C" value={formatNumber(displayed.close)} />
            <LegendValue label="Vol" value={formatInteger(displayed.volume)} />
            <LegendValue label="SMA20" value={formatNumber(displayed.sma20)} />
            <LegendValue label="SMA50" value={formatNumber(displayed.sma50)} />
            <LegendValue label="RSI14" value={formatNumber(displayed.rsi14)} />
          </>
        ) : (
          <span className="text-[var(--text-tertiary)]">No data loaded.</span>
        )}
      </div>
      <div style={{ height }} ref={containerRef} data-testid="price-chart" />
    </div>
  )
}
