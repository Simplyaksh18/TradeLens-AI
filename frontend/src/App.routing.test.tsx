import { describe, expect, it, vi, afterEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import App from './App'
import { mockFetchForAuthState, renderWithProviders, TEST_USER } from './test/authTestUtils'

describe('App routing (authenticated)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it.each([
    ['/', 'Overview'],
    ['/data-explorer', 'Data Explorer'],
    ['/strategy-lab', 'Strategy Lab'],
    ['/backtests', 'Backtests'],
    ['/trade-auditor', 'Strategy Auditor'],
    ['/failure-investigator', 'Strategy Failure Investigator'],
    ['/research', 'Research Workspace'],
    ['/settings', 'Settings'],
    ['/docs', 'Documentation'],
  ])('renders the correct page for %s when signed in', async (path, expectedHeading) => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: [path] })
    await waitFor(() => expect(screen.getByRole('heading', { name: expectedHeading })).toBeInTheDocument())
  })

  it('renders a 404 page for an unknown route when signed in', async () => {
    mockFetchForAuthState(TEST_USER)
    renderWithProviders(<App />, { initialEntries: ['/this-route-does-not-exist'] })
    await waitFor(() => expect(screen.getByText('Research route not found')).toBeInTheDocument())
  })

  it('changes the rendered page when a sidebar link is clicked', async () => {
    mockFetchForAuthState(TEST_USER)
    const user = userEvent.setup()
    renderWithProviders(<App />, { initialEntries: ['/'] })
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Overview' })).toBeInTheDocument())

    await user.click(screen.getAllByRole('link', { name: /data explorer/i })[0])

    expect(screen.getByRole('heading', { name: 'Data Explorer' })).toBeInTheDocument()
  })
})

describe('App routing (unauthenticated)', () => {
  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('redirects an unauthenticated user from a protected route to /login', async () => {
    mockFetchForAuthState(null)
    renderWithProviders(<App />, { initialEntries: ['/strategy-lab'] })
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument())
  })

  it('redirects an unauthenticated user from /failure-investigator to /login', async () => {
    mockFetchForAuthState(null)
    renderWithProviders(<App />, { initialEntries: ['/failure-investigator'] })
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument())
  })

  it('renders /login without authentication', async () => {
    mockFetchForAuthState(null)
    renderWithProviders(<App />, { initialEntries: ['/login'] })
    await waitFor(() => expect(screen.getByRole('heading', { name: 'Welcome back' })).toBeInTheDocument())
  })

  it('renders /signup without authentication', async () => {
    mockFetchForAuthState(null)
    renderWithProviders(<App />, { initialEntries: ['/signup'] })
    await waitFor(() =>
      expect(screen.getByRole('heading', { name: 'Create your account' })).toBeInTheDocument(),
    )
  })
})
