import { getMarketData } from '../api/marketData'
import { useApiResource } from './useApiResource'

export function useMarketData(symbol: string | null, start: string, end: string, interval = '1d') {
  return useApiResource(
    (signal) => getMarketData({ symbol: symbol as string, start, end, interval, signal }),
    [symbol, start, end, interval],
    Boolean(symbol && start && end),
  )
}
