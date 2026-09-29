import { apiGet } from './client'
import type { StrategyAuditResponse } from './types'

export const TREND_MOMENTUM_V1 = 'trend-momentum-v1'

export interface AuditRequest {
  symbol: string
  start: string
  end: string
  interval?: string
  auditDate: string
  signal?: AbortSignal
}

/** Phase 3D: `start` is the lower bound of the historical evidence window
 * (prior BUY signals), not a calculation-history bound — the backend
 * internally widens its own market-data fetch for indicator warm-up (see
 * CLAUDE.md Phase 3D). `audit_date` is required; the backend rejects a
 * non-trading-bar date with 422 AUDIT_DATE_NOT_A_TRADING_BAR rather than
 * silently remapping it. */
export function getTrendMomentumV1Audit({
  symbol,
  start,
  end,
  interval = '1d',
  auditDate,
  signal,
}: AuditRequest): Promise<StrategyAuditResponse> {
  return apiGet<StrategyAuditResponse>(`/api/v1/audits/${TREND_MOMENTUM_V1}/${encodeURIComponent(symbol)}`, {
    params: { start, end, interval, audit_date: auditDate },
    signal,
  })
}
