import { getTrendMomentumV1Audit } from '../api/audits'
import { useApiResource } from './useApiResource'

export function useStrategyAudit(symbol: string | null, start: string, end: string, auditDate: string, interval = '1d') {
  return useApiResource(
    (signal) => getTrendMomentumV1Audit({ symbol: symbol as string, start, end, interval, auditDate, signal }),
    [symbol, start, end, auditDate, interval],
    Boolean(symbol && start && end && auditDate),
  )
}
