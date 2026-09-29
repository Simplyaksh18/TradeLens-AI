import { getTrendMomentumV1Outcomes } from '../api/outcomes'
import { useApiResource } from './useApiResource'

export function useSignalOutcomes(symbol: string | null, start: string, end: string, interval = '1d') {
  return useApiResource(
    (signal) => getTrendMomentumV1Outcomes({ symbol: symbol as string, start, end, interval, signal }),
    [symbol, start, end, interval],
    Boolean(symbol && start && end),
  )
}
