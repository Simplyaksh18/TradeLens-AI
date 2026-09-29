import { useEffect, useRef, useState } from 'react'
import { searchInstruments } from '../api/instruments'
import { AbortedRequestError, ApiError } from '../api/client'
import type { Instrument } from '../api/types'
import { useDebouncedValue } from './useDebouncedValue'

interface UseInstrumentSearchResult {
  results: Instrument[]
  loading: boolean
  error: ApiError | null
}

/** Debounced, abort-safe instrument search. A stale in-flight response can
 * never overwrite a newer query's results. */
export function useInstrumentSearch(query: string, limit = 20): UseInstrumentSearchResult {
  const debouncedQuery = useDebouncedValue(query.trim(), 300)
  const [results, setResults] = useState<Instrument[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<ApiError | null>(null)
  const abortRef = useRef<AbortController | null>(null)

  useEffect(() => {
    abortRef.current?.abort()

    if (debouncedQuery.length === 0) {
      setResults([])
      setLoading(false)
      setError(null)
      return
    }

    const controller = new AbortController()
    abortRef.current = controller
    setLoading(true)
    setError(null)

    searchInstruments(debouncedQuery, { limit, signal: controller.signal })
      .then((response) => {
        setResults(response.results)
        setLoading(false)
      })
      .catch((err) => {
        if (err instanceof AbortedRequestError) return
        setError(err instanceof ApiError ? err : new ApiError(0, 'UNKNOWN_ERROR', 'Search failed.'))
        setLoading(false)
      })

    return () => controller.abort()
  }, [debouncedQuery, limit])

  return { results, loading, error }
}
