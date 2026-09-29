import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Routes, Route } from 'react-router-dom'
import SignupPage from './SignupPage'
import OverviewPage from '../OverviewPage'
import * as authApi from '../../api/auth'
import { renderWithProviders, mockFetchForAuthState, TEST_USER } from '../../test/authTestUtils'

function renderSignupRoute() {
  mockFetchForAuthState(null)
  return renderWithProviders(
    <Routes>
      <Route path="/signup" element={<SignupPage />} />
      <Route path="/" element={<OverviewPage />} />
    </Routes>,
    { initialEntries: ['/signup'] },
  )
}

async function fillValidForm(user: ReturnType<typeof userEvent.setup>) {
  await user.type(screen.getByLabelText('Full name'), 'Akshi Kumar')
  await user.type(screen.getByLabelText('Display name'), 'Akshi')
  await user.type(screen.getByLabelText('Email'), 'akshi@example.com')
}

describe('SignupPage', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('renders with research-purpose context', async () => {
    renderSignupRoute()
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Create your account' })).toBeInTheDocument())
    expect(screen.getByText('Research & Education Only')).toBeInTheDocument()
  })

  it('rejects a password shorter than 8 characters before calling the API', async () => {
    renderSignupRoute()
    await waitFor(() => screen.getByRole('heading', { name: 'Create your account' }))
    const registerSpy = vi.spyOn(authApi, 'register')

    const user = userEvent.setup()
    await fillValidForm(user)
    await user.type(screen.getByLabelText('Password'), 'short')
    await user.type(screen.getByLabelText('Confirm password'), 'short')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/at least 8 characters/i)
    expect(registerSpy).not.toHaveBeenCalled()
  })

  it('rejects mismatched password confirmation before calling the API', async () => {
    renderSignupRoute()
    await waitFor(() => screen.getByRole('heading', { name: 'Create your account' }))
    const registerSpy = vi.spyOn(authApi, 'register')

    const user = userEvent.setup()
    await fillValidForm(user)
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.type(screen.getByLabelText('Confirm password'), 'different123')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    expect(await screen.findByRole('alert')).toHaveTextContent(/do not match/i)
    expect(registerSpy).not.toHaveBeenCalled()
  })

  it('registers with valid input and navigates to Overview', async () => {
    renderSignupRoute()
    await waitFor(() => screen.getByRole('heading', { name: 'Create your account' }))
    vi.spyOn(authApi, 'register').mockResolvedValue(TEST_USER)

    const user = userEvent.setup()
    await fillValidForm(user)
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.type(screen.getByLabelText('Confirm password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Create account' }))

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Overview' })).toBeInTheDocument())
  })

  it('has a link to sign in', async () => {
    renderSignupRoute()
    await waitFor(() => screen.getByRole('heading', { name: 'Create your account' }))
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
  })
})
