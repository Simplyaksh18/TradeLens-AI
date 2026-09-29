import { apiGet } from './client'
import type { HealthResponse } from './types'

export function getHealth(options: { signal?: AbortSignal } = {}): Promise<HealthResponse> {
  return apiGet<HealthResponse>('/api/v1/health', { signal: options.signal })
}
