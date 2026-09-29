import { apiGet } from './client'
import type { Instrument, InstrumentSearchResponse } from './types'

export function searchInstruments(
  query: string,
  options: { limit?: number; signal?: AbortSignal } = {},
): Promise<InstrumentSearchResponse> {
  return apiGet<InstrumentSearchResponse>('/api/v1/instruments', {
    params: { q: query, limit: options.limit ?? 20 },
    signal: options.signal,
  })
}

export function getInstrument(symbol: string, options: { signal?: AbortSignal } = {}): Promise<Instrument> {
  return apiGet<Instrument>(`/api/v1/instruments/${encodeURIComponent(symbol)}`, {
    signal: options.signal,
  })
}
