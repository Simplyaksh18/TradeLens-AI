import { getTrendMomentumV1Investigation } from '../api/investigations'
import { useApiResource } from './useApiResource'

export function useStrategyFailureInvestigation(symbol: string | null, start: string, end: string, interval = '1d') {
  return useApiResource(
    (signal) => getTrendMomentumV1Investigation({ symbol: symbol as string, start, end, interval, signal }),
    [symbol, start, end, interval],
    Boolean(symbol && start && end),
  )
}
