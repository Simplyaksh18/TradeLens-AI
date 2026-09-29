import { getTrendMomentumV1 } from '../api/strategies'
import { useApiResource } from './useApiResource'

export function useStrategyEvaluations(symbol: string | null, start: string, end: string, interval = '1d') {
  return useApiResource(
    (signal) => getTrendMomentumV1({ symbol: symbol as string, start, end, interval, signal }),
    [symbol, start, end, interval],
    Boolean(symbol && start && end),
  )
}
