import { getTrendMomentumV1Analytics } from '../api/analytics'
import { useApiResource } from './useApiResource'

export function usePerformanceAnalytics(symbol: string | null, start: string, end: string, initialCapital: number, interval = '1d') {
  return useApiResource(
    (signal) => getTrendMomentumV1Analytics({ symbol: symbol as string, start, end, interval, initialCapital, signal }),
    [symbol, start, end, initialCapital, interval],
    Boolean(symbol && start && end),
  )
}
