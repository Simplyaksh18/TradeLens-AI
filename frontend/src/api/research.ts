import { apiPost } from './client'
import type { ResearchRequest, ResearchResponse } from './types'

/** Phase 5E: one research question -> one structured result. No
 * conversation history, no streaming -- a single POST per submission. */
export function postResearchQuestion(question: string, signal?: AbortSignal): Promise<ResearchResponse> {
  const body: ResearchRequest = { question }
  return apiPost<ResearchResponse>('/api/v1/research', body, { signal })
}
