import { apiGet } from './client'
import type { MarketDataResponse } from './types'

export interface HistoryRequest {
  symbol: string
  start: string
  end: string
  interval?: string
  signal?: AbortSignal
}

export function getMarketData({ symbol, start, end, interval = '1d', signal }: HistoryRequest): Promise<MarketDataResponse> {
  return apiGet<MarketDataResponse>(`/api/v1/market-data/${encodeURIComponent(symbol)}`, {
    params: { start, end, interval },
    signal,
  })
}
