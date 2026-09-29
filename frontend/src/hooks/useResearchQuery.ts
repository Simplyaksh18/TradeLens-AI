import { useCallback, useRef, useState } from 'react'
import { AbortedRequestError, ApiError } from '../api/client'
import { postResearchQuestion } from '../api/research'
import type { ResearchResponse } from '../api/types'

export interface ResearchQueryState {
  data: ResearchResponse | null
  loading: boolean
  error: ApiError | null
}

/** Manual-trigger request state (unlike `useApiResource`, which auto-fires
 * on dependency change) -- one research question is submitted at a time
 * via `run(question)`. A newer `run()` call aborts any still-in-flight
 * previous request so a stale response can never overwrite newer state. */
export function useResearchQuery() {
  const [state, setState] = useState<ResearchQueryState>({ data: null, loading: false, error: null })
  const abortRef = useRef<AbortController | null>(null)

  const run = useCallback((question: string) => {
    abortRef.current?.abort()
    const controller = new AbortController()
    abortRef.current = controller
    setState({ data: null, loading: true, error: null })

    postResearchQuestion(question, controller.signal)
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((err) => {
        if (err instanceof AbortedRequestError) return
        setState({
          data: null,
          loading: false,
          error: err instanceof ApiError ? err : new ApiError(0, 'UNKNOWN_ERROR', 'Request failed.'),
        })
      })
  }, [])

  return { ...state, run }
}
