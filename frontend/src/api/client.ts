import type { ApiErrorBody } from './types'

export const API_BASE_URL: string =
  import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export class ApiError extends Error {
  readonly code: string
  readonly status: number

  constructor(status: number, code: string, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.code = code
  }
}

/** Thrown when a request is intentionally aborted (e.g. a newer request
 * superseded it) — callers should treat this as "ignore", not as an error
 * to display. */
export class AbortedRequestError extends Error {
  constructor() {
    super('Request aborted')
    this.name = 'AbortedRequestError'
  }
}

interface RequestOptions {
  params?: Record<string, string | number | undefined>
  signal?: AbortSignal
}

function buildUrl(path: string, params?: RequestOptions['params']): string {
  const url = new URL(path, API_BASE_URL)
  if (params) {
    for (const [key, value] of Object.entries(params)) {
      if (value !== undefined) url.searchParams.set(key, String(value))
    }
  }
  return url.toString()
}

async function request<T>(
  method: 'GET' | 'POST' | 'PATCH',
  path: string,
  options: RequestOptions & { body?: unknown } = {},
): Promise<T> {
  const url = buildUrl(path, options.params)
  let response: Response
  try {
    response = await fetch(url, {
      method,
      signal: options.signal,
      // Auth uses an HttpOnly session cookie (see backend Phase 1G) rather
      // than a token in localStorage — every request must include it.
      credentials: 'include',
      headers: options.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    })
  } catch (err) {
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new AbortedRequestError()
    }
    throw new ApiError(0, 'NETWORK_ERROR', 'Could not reach the TradeLens API.')
  }

  if (!response.ok) {
    let body: ApiErrorBody | null = null
    try {
      body = (await response.json()) as ApiErrorBody
    } catch {
      // response body wasn't JSON; fall through to a generic message
    }
    const code = body?.error?.code ?? 'UNKNOWN_ERROR'
    const message = body?.error?.message ?? `Request failed with status ${response.status}.`
    throw new ApiError(response.status, code, message)
  }

  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function apiGet<T>(path: string, options: RequestOptions = {}): Promise<T> {
  return request<T>('GET', path, options)
}

export function apiPost<T>(path: string, body?: unknown, options: RequestOptions = {}): Promise<T> {
  return request<T>('POST', path, { ...options, body: body ?? {} })
}

export function apiPatch<T>(path: string, body?: unknown, options: RequestOptions = {}): Promise<T> {
  return request<T>('PATCH', path, { ...options, body: body ?? {} })
}
