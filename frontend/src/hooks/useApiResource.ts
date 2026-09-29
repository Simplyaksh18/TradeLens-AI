import { useEffect, useRef, useState } from 'react'
import { AbortedRequestError, ApiError } from '../api/client'

export interface ApiResourceState<T> {
  data: T | null
  loading: boolean
  error: ApiError | null
}

/** Generic abort-safe resource fetcher: `fetcher` is called whenever any of
 * `deps` changes; an in-flight request that gets superseded is aborted so
 * its (eventually arriving) response can never overwrite newer state. Pass
 * `enabled: false` to skip fetching (e.g. no symbol selected yet). */
export function useApiResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  deps: unknown[],
  enabled: boolean,
): ApiResourceState<T> {
  const [state, setState] = useState<ApiResourceState<T>>({ data: null, loading: false, error: null })
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    abortRef.current?.abort()

    if (!enabled) {
      setState({ data: null, loading: false, error: null })
      return
    }

    const controller = new AbortController()
    abortRef.current = controller
    setState((prev) => ({ ...prev, loading: true, error: null }))

    fetcher(controller.signal)
      .then((data) => setState({ data, loading: false, error: null }))
      .catch((err) => {
        if (err instanceof AbortedRequestError) return
        setState({
          data: null,
          loading: false,
          error: err instanceof ApiError ? err : new ApiError(0, 'UNKNOWN_ERROR', 'Request failed.'),
        })
      })

    return () => controller.abort()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, enabled])

  return state
}
