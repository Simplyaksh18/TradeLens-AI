import { getIndicators } from '../api/indicators'
import { useApiResource } from './useApiResource'

export function useIndicators(symbol: string | null, start: string, end: string, interval = '1d') {
  return useApiResource(
    (signal) => getIndicators({ symbol: symbol as string, start, end, interval, signal }),
    [symbol, start, end, interval],
    Boolean(symbol && start && end),
  )
}
