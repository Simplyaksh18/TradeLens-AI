import { getTrendMomentumV1Backtest } from '../api/backtests'
import { useApiResource } from './useApiResource'

export function useBacktestResult(symbol: string | null, start: string, end: string, initialCapital: number, interval = '1d') {
  return useApiResource(
    (signal) => getTrendMomentumV1Backtest({ symbol: symbol as string, start, end, interval, initialCapital, signal }),
    [symbol, start, end, initialCapital, interval],
    Boolean(symbol && start && end),
  )
}
