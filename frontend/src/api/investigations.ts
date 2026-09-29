import { apiGet } from './client'
import type { StrategyFailureInvestigationResponse } from './types'

export const TREND_MOMENTUM_V1 = 'trend-momentum-v1'

export interface InvestigationRequest {
  symbol: string
  start: string
  end: string
  interval?: string
  signal?: AbortSignal
}

/** Phase 4E: `start`/`end` define the historical BUY-signal investigation
 * POPULATION (both inclusive) -- not a single point-in-time decision like
 * the Strategy Auditor. The backend internally widens its own market-data
 * fetch for indicator warm-up so signals near `start` are never starved
 * (see CLAUDE.md Phase 4E); that widening is entirely a backend concern. */
export function getTrendMomentumV1Investigation({
  symbol,
  start,
  end,
  interval = '1d',
  signal,
}: InvestigationRequest): Promise<StrategyFailureInvestigationResponse> {
  return apiGet<StrategyFailureInvestigationResponse>(`/api/v1/investigations/${TREND_MOMENTUM_V1}/${encodeURIComponent(symbol)}`, {
    params: { start, end, interval },
    signal,
  })
}
