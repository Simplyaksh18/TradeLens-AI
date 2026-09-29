import { describe, expect, it, vi, beforeEach, afterEach } from 'vitest'
import { apiGet, ApiError, AbortedRequestError, API_BASE_URL } from './client'

describe('apiGet', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('constructs the correct URL with query parameters', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(new Response(JSON.stringify({ ok: true }), { status: 200 }))
    vi.stubGlobal('fetch', fetchSpy)

    await apiGet('/api/v1/instruments', { params: { q: 'REL', limit: 20 } })

    const calledUrl = fetchSpy.mock.calls[0][0] as string
    expect(calledUrl).toBe(`${API_BASE_URL}/api/v1/instruments?q=REL&limit=20`)
  })

  it('omits undefined query parameters', async () => {
    const fetchSpy = vi.fn().mockResolvedValue(new Response(JSON.stringify({}), { status: 200 }))
    vi.stubGlobal('fetch', fetchSpy)

    await apiGet('/api/v1/health', { params: { foo: undefined } })

    const calledUrl = fetchSpy.mock.calls[0][0] as string
    expect(calledUrl).not.toContain('foo')
  })

  it('parses the structured error body on a non-ok response', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { code: 'INSTRUMENT_NOT_FOUND', message: 'Not found.' } }), {
          status: 404,
        }),
      ),
    )

    await expect(apiGet('/api/v1/instruments/NOTREAL')).rejects.toMatchObject({
      code: 'INSTRUMENT_NOT_FOUND',
      status: 404,
      message: 'Not found.',
    })
  })

  it('falls back to a generic error when the body is not JSON', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('not json', { status: 500 })))

    await expect(apiGet('/api/v1/health')).rejects.toBeInstanceOf(ApiError)
  })

  it('distinguishes a reached-but-failed 5xx from an unreachable network failure when no JSON body is present', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('', { status: 502 })))

    await expect(apiGet('/api/v1/health')).rejects.toMatchObject({
      status: 502,
      message: expect.stringContaining('reached'),
    })
  })

  it('always prefers the backend structured error body over the generic 5xx fallback', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue(
        new Response(JSON.stringify({ error: { code: 'INSTRUMENT_CATALOG_UNAVAILABLE', message: 'Catalogue unavailable.' } }), {
          status: 503,
        }),
      ),
    )

    await expect(apiGet('/api/v1/instruments')).rejects.toMatchObject({
      code: 'INSTRUMENT_CATALOG_UNAVAILABLE',
      message: 'Catalogue unavailable.',
    })
  })

  it('throws AbortedRequestError when the request is aborted', async () => {
    const abortError = new DOMException('aborted', 'AbortError')
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(abortError))

    await expect(apiGet('/api/v1/health')).rejects.toBeInstanceOf(AbortedRequestError)
  })

  it('surfaces a network error distinctly from a domain error', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(apiGet('/api/v1/health')).rejects.toMatchObject({ code: 'NETWORK_ERROR' })
  })
})
