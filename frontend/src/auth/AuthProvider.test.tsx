import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { StrictMode } from 'react'
import { AuthProvider } from './AuthProvider'
import { useAuth } from './useAuth'
import * as authApi from '../api/auth'
import { AbortedRequestError } from '../api/client'
import { TEST_USER } from '../test/authTestUtils'

function Probe() {
  const { user, status } = useAuth()
  return (
    <div>
      <span data-testid="status">{status}</span>
      <span data-testid="user">{user?.display_name ?? ''}</span>
    </div>
  )
}

describe('AuthProvider mount-time session check', () => {
  it('does not treat an aborted (superseded) request as "unauthenticated"', async () => {
    // Simulates React StrictMode's double-effect-invocation in development:
    // the first mount's request is aborted by cleanup; only the second
    // mount's request actually completes. Regression for a real bug found
    // via manual testing: a refresh right after registering bounced a
    // genuinely authenticated user back to /login.
    let callCount = 0
    vi.spyOn(authApi, 'getCurrentUser').mockImplementation(() => {
      callCount += 1
      if (callCount === 1) return Promise.reject(new AbortedRequestError())
      return Promise.resolve(TEST_USER)
    })

    render(
      <StrictMode>
        <AuthProvider>
          <Probe />
        </AuthProvider>
      </StrictMode>,
    )

    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('authenticated'))
    expect(screen.getByTestId('user').textContent).toBe('Akshi')
  })

  it('treats a genuine 401 as "unauthenticated"', async () => {
    const { ApiError } = await import('../api/client')
    vi.spyOn(authApi, 'getCurrentUser').mockRejectedValue(new ApiError(401, 'SESSION_INVALID', 'Not signed in.'))

    render(
      <AuthProvider>
        <Probe />
      </AuthProvider>,
    )

    await waitFor(() => expect(screen.getByTestId('status').textContent).toBe('unauthenticated'))
  })
})
