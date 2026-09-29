import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Routes, Route } from 'react-router-dom'
import { UserMenu } from './UserMenu'
import LoginPage from '../../pages/auth/LoginPage'
import * as authApi from '../../api/auth'
import { renderWithProviders, mockFetchForAuthState, TEST_USER } from '../../test/authTestUtils'

function renderUserMenu() {
  mockFetchForAuthState(TEST_USER)
  return renderWithProviders(
    <Routes>
      <Route path="/" element={<UserMenu />} />
      <Route path="/login" element={<LoginPage />} />
    </Routes>,
    { initialEntries: ['/'] },
  )
}

describe('UserMenu', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('shows initials when no avatar is set', async () => {
    renderUserMenu()
    await waitFor(() => expect(screen.getByRole('button', { name: /open user menu/i })).toBeInTheDocument())
    expect(screen.getByText('A')).toBeInTheDocument() // "Akshi" -> single-word initial
  })

  it('opens to show name, email, and menu actions', async () => {
    renderUserMenu()
    const user = userEvent.setup()
    await waitFor(() => screen.getByRole('button', { name: /open user menu/i }))
    await user.click(screen.getByRole('button', { name: /open user menu/i }))

    expect(screen.getByText('Akshi')).toBeInTheDocument()
    expect(screen.getByText('akshi@example.com')).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /profile & settings/i })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: /sign out/i })).toBeInTheDocument()
  })

  it('signs out and navigates to /login', async () => {
    vi.spyOn(authApi, 'logout').mockResolvedValue(undefined)
    renderUserMenu()
    const user = userEvent.setup()

    await waitFor(() => screen.getByRole('button', { name: /open user menu/i }))
    await user.click(screen.getByRole('button', { name: /open user menu/i }))
    await user.click(screen.getByRole('menuitem', { name: /sign out/i }))

    await waitFor(() => expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument())
  })
})
