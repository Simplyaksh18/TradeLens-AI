import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Routes, Route } from 'react-router-dom'
import LoginPage from './LoginPage'
import OverviewPage from '../OverviewPage'
import * as authApi from '../../api/auth'
import { ApiError } from '../../api/client'
import { renderWithProviders, mockFetchForAuthState } from '../../test/authTestUtils'
import { TEST_USER } from '../../test/authTestUtils'

function renderLoginRoute() {
  mockFetchForAuthState(null)
  return renderWithProviders(
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/" element={<OverviewPage />} />
    </Routes>,
    { initialEntries: ['/login'] },
  )
}

describe('LoginPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders with product/research-purpose information and a Google button area', async () => {
    renderLoginRoute()
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument())

    expect(screen.getByText('TradeLens')).toBeInTheDocument()
    expect(screen.getByText('Research & Education Only')).toBeInTheDocument()
    expect(screen.getByText(/not a brokerage service/i)).toBeInTheDocument()
    expect(screen.getByText('Continue with Google')).toBeInTheDocument()
  })

  it('logs in with valid local credentials and navigates to Overview', async () => {
    renderLoginRoute()
    await waitFor(() => screen.getByRole('heading', { name: 'Welcome back' }))
    vi.spyOn(authApi, 'login').mockResolvedValue(TEST_USER)

    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Email'), 'akshi@example.com')
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Overview' })).toBeInTheDocument())
  })

  it('shows a safe error message for invalid credentials, not a raw backend/traceback string', async () => {
    renderLoginRoute()
    await waitFor(() => screen.getByRole('heading', { name: 'Welcome back' }))
    vi.spyOn(authApi, 'login').mockRejectedValue(new ApiError(401, 'INVALID_CREDENTIALS', 'Invalid email or password.'))

    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Email'), 'akshi@example.com')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Invalid email or password.'))
    expect(screen.queryByText(/traceback/i)).not.toBeInTheDocument()
  })

  it('shows a generic message when the backend is unavailable', async () => {
    renderLoginRoute()
    await waitFor(() => screen.getByRole('heading', { name: 'Welcome back' }))
    vi.spyOn(authApi, 'login').mockRejectedValue(new ApiError(0, 'NETWORK_ERROR', 'Could not reach the TradeLens API.'))

    const user = userEvent.setup()
    await user.type(screen.getByLabelText('Email'), 'akshi@example.com')
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))

    await waitFor(() => expect(screen.getByRole('alert')).toHaveTextContent('Could not reach the TradeLens API.'))
  })

  it('has a link to create an account', async () => {
    renderLoginRoute()
    await waitFor(() => screen.getByRole('heading', { name: 'Welcome back' }))
    expect(screen.getByRole('link', { name: 'Create account' })).toHaveAttribute('href', '/signup')
  })
})
