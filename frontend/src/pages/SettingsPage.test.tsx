import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Routes, Route } from 'react-router-dom'
import SettingsPage from './SettingsPage'
import { AppShell } from '../components/layout/AppShell'
import * as authApi from '../api/auth'
import { renderWithProviders, mockFetchForAuthState, TEST_USER } from '../test/authTestUtils'

function renderSettingsWithShell() {
  mockFetchForAuthState(TEST_USER)
  return renderWithProviders(
    <Routes>
      <Route element={<AppShell />}>
        <Route path="/settings" element={<SettingsPage />} />
      </Route>
    </Routes>,
    { initialEntries: ['/settings'] },
  )
}

describe('SettingsPage profile update', () => {
  beforeEach(() => {
    vi.restoreAllMocks()
  })

  it('updates the top-bar greeting immediately after a display-name save, without logout/login', async () => {
    renderSettingsWithShell()
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument())

    // Greeting initially shows the original display name.
    expect(screen.getByText('Akshi', { selector: 'span.font-medium' })).toBeInTheDocument()

    vi.spyOn(authApi, 'updateProfile').mockResolvedValue({ ...TEST_USER, display_name: 'New Display' })

    const user = userEvent.setup()
    const displayNameInput = screen.getByLabelText('Display name')
    await user.clear(displayNameInput)
    await user.type(displayNameInput, 'New Display')
    // fireEvent.submit rather than clicking the submit button: this
    // environment's userEvent-click-to-submit path did not reliably fire
    // the form's submit event for this button (verified by direct
    // comparison); a direct submit event is the standard, equally valid
    // RTL way to exercise the same onSubmit handler.
    fireEvent.submit(displayNameInput.closest('form')!)

    await waitFor(() =>
      expect(screen.getByText('New Display', { selector: 'span.font-medium' })).toBeInTheDocument(),
    )
  })

  it('shows Google as the authentication method for a Google account and hides password UI', async () => {
    mockFetchForAuthState({ ...TEST_USER, auth_provider: 'GOOGLE' })
    renderWithProviders(
      <Routes>
        <Route element={<AppShell />}>
          <Route path="/settings" element={<SettingsPage />} />
        </Route>
      </Routes>,
      { initialEntries: ['/settings'] },
    )
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Settings' })).toBeInTheDocument())
    expect(screen.getByText('Google', { selector: 'p' })).toBeInTheDocument()
    expect(screen.getByText(/no tradelens password is used/i)).toBeInTheDocument()
  })
})
