import { useState } from 'react'
import { Download } from 'lucide-react'
import { PageHeader } from '../components/layout/PageHeader'
import { ResearchToolbar, type ResearchSelection } from '../components/research/ResearchToolbar'
import { Card, SectionLabel } from '../components/ui/Card'
import { ApiErrorState, LoadingSkeleton, NothingSelectedState, NoDataState } from '../components/ui/States'
import { PriceChart } from '../components/charts/PriceChart'
import { OHLCVTable } from '../components/tables/OHLCVTable'
import { useMarketData } from '../hooks/useMarketData'
import { formatDate, formatInteger } from '../utils/format'
import { buildOhlcvFilename, downloadCsv, ohlcvToCsv } from '../utils/csvExport'

export default function DataExplorerPage() {
  const [selection, setSelection] = useState<ResearchSelection | null>(null)
  const symbol = selection?.instrument.symbol ?? null
  const start = selection?.start ?? ''
  const end = selection?.end ?? ''

  const marketData = useMarketData(symbol, start, end)
  const bars = marketData.data?.bars ?? []

  const zeroVolumeCount = bars.filter((b) => b.volume === 0).length

  function handleExport() {
    if (!selection || bars.length === 0) return
    const csv = ohlcvToCsv(bars)
    downloadCsv(buildOhlcvFilename(selection.instrument.symbol, selection.start, selection.end, selection.interval), csv)
  }

  return (
    <div className="space-y-6">
      <PageHeader title="Data Explorer" description="Inspect the normalized historical OHLCV dataset behind TradeLens." />

      <ResearchToolbar onLoad={setSelection} />

      {!selection && <NothingSelectedState message="Select an instrument and date range, then Load Data to inspect it." />}

      {selection && marketData.loading && (
        <Card className="p-6">
          <LoadingSkeleton lines={4} />
        </Card>
      )}

      {selection && marketData.error && <ApiErrorState error={marketData.error} />}

      {selection && marketData.data && bars.length === 0 && (
        <NoDataState message="No market data was returned for this instrument and period." />
      )}

      {selection && marketData.data && bars.length > 0 && (
        <div className="space-y-4">
          <Card className="grid grid-cols-2 gap-4 p-4 sm:grid-cols-4">
            <div>
              <SectionLabel>Provider Symbol</SectionLabel>
              <p className="font-mono-tabular text-sm">{marketData.data.provider_symbol}</p>
            </div>
            <div>
              <SectionLabel>Interval</SectionLabel>
              <p className="text-sm">1D</p>
            </div>
            <div>
              <SectionLabel>Record Count</SectionLabel>
              <p className="font-mono-tabular text-sm">{formatInteger(bars.length)}</p>
            </div>
            <div>
              <SectionLabel>Coverage</SectionLabel>
              <p className="font-mono-tabular text-sm">
                {formatDate(bars[0].date)} → {formatDate(bars.at(-1)!.date)}
              </p>
            </div>
          </Card>

          <Card className="p-4">
            <SectionLabel>Data Observations</SectionLabel>
            <p className="mt-1 text-sm text-[var(--text-secondary)]">
              Rows loaded: {formatInteger(bars.length)} · Zero-volume rows: {formatInteger(zeroVolumeCount)}
            </p>
          </Card>

          <Card className="p-4">
            <SectionLabel>Chart Preview</SectionLabel>
            <div className="mt-2">
              <PriceChart bars={bars} height={320} />
            </div>
          </Card>

          <Card className="p-4">
            <div className="mb-2 flex items-center justify-between">
              <SectionLabel>OHLCV Table</SectionLabel>
              <button
                type="button"
                onClick={handleExport}
                className="flex items-center gap-1.5 rounded-md border border-[var(--border)] px-3 py-1.5 text-xs font-medium hover:bg-[var(--surface-2)]"
              >
                <Download size={13} aria-hidden="true" />
                Export CSV
              </button>
            </div>
            <OHLCVTable bars={bars} />
          </Card>
        </div>
      )}
    </div>
  )
}
