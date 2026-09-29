import { apiGet } from './client'
import type { IndicatorResponse } from './types'
import type { HistoryRequest } from './marketData'

export function getIndicators({ symbol, start, end, interval = '1d', signal }: HistoryRequest): Promise<IndicatorResponse> {
  return apiGet<IndicatorResponse>(`/api/v1/indicators/${encodeURIComponent(symbol)}`, {
    params: { start, end, interval },
    signal,
  })
}
