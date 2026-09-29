import { vi } from 'vitest'
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import type { ReactElement } from 'react'
import { ThemeProvider } from '../theme/ThemeProvider'
import { AuthProvider } from '../auth/AuthProvider'
import type { AuthUser } from '../api/types'

export const TEST_USER: AuthUser = {
  id: 'user-1',
  email: 'akshi@example.com',
  full_name: 'Akshi Kumar',
  display_name: 'Akshi',
  avatar_url: null,
  auth_provider: 'LOCAL',
}

/** Mocks global fetch so AuthProvider's mount-time GET /api/v1/auth/me
 * resolves to either a signed-in user or a 401, without any real network
 * call. Also handles /api/v1/health (used by TopBar) so it doesn't error. */
export function mockFetchForAuthState(user: AuthUser | null) {
  const fetchMock = vi.fn().mockImplementation((input: RequestInfo | URL) => {
    const url = typeof input === 'string' ? input : input.toString()
    if (url.includes('/api/v1/auth/me')) {
      if (user) {
        return Promise.resolve(new Response(JSON.stringify(user), { status: 200 }))
      }
      return Promise.resolve(
        new Response(JSON.stringify({ error: { code: 'SESSION_INVALID', message: 'Not signed in.' } }), {
          status: 401,
        }),
      )
    }
    if (url.includes('/api/v1/health')) {
      return Promise.resolve(
        new Response(JSON.stringify({ status: 'ok', service: 'TradeLens API', version: '0.1.0' }), { status: 200 }),
      )
    }
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }))
  })
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

export function renderWithProviders(ui: ReactElement, { initialEntries = ['/'] }: { initialEntries?: string[] } = {}) {
  return render(
    <ThemeProvider>
      <AuthProvider>
        <MemoryRouter initialEntries={initialEntries}>{ui}</MemoryRouter>
      </AuthProvider>
    </ThemeProvider>,
  )
}
