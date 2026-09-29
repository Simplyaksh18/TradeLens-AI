import { describe, expect, it, beforeEach, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ThemeProvider } from './ThemeProvider'
import { useTheme } from './useTheme'

function Probe() {
  const { preference, setPreference, toggle } = useTheme()
  return (
    <div>
      <span data-testid="preference">{preference}</span>
      <button onClick={() => setPreference('light')}>light</button>
      <button onClick={() => setPreference('dark')}>dark</button>
      <button onClick={toggle}>toggle</button>
    </div>
  )
}

function mockMatchMedia(prefersDark: boolean) {
  window.matchMedia = vi.fn().mockImplementation((query: string) => ({
    matches: query.includes('dark') ? prefersDark : false,
    media: query,
    addEventListener: vi.fn(),
    removeEventListener: vi.fn(),
  })) as unknown as typeof window.matchMedia
}

describe('ThemeProvider', () => {
  beforeEach(() => {
    window.localStorage.clear()
    document.documentElement.removeAttribute('data-theme')
    mockMatchMedia(false)
  })

  it('light selection updates preference and the DOM attribute', async () => {
    const user = userEvent.setup()
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    )
    await user.click(screen.getByRole('button', { name: 'light' }))
    expect(screen.getByTestId('preference').textContent).toBe('light')
    expect(document.documentElement.getAttribute('data-theme')).toBe('light')
  })

  it('dark selection updates preference and the DOM attribute', async () => {
    const user = userEvent.setup()
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    )
    await user.click(screen.getByRole('button', { name: 'dark' }))
    expect(screen.getByTestId('preference').textContent).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('toggle flips between light and dark', async () => {
    const user = userEvent.setup()
    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    )
    const before = screen.getByTestId('preference').textContent
    await user.click(screen.getByRole('button', { name: 'toggle' }))
    const after = screen.getByTestId('preference').textContent
    expect(after).not.toBe(before)
    expect(['light', 'dark']).toContain(after)
  })

  it('persists the chosen preference and restores it on remount', async () => {
    const user = userEvent.setup()
    const { unmount } = render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    )
    await user.click(screen.getByRole('button', { name: 'dark' }))
    expect(window.localStorage.getItem('tradelens.theme')).toBe('dark')
    unmount()

    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    )
    expect(screen.getByTestId('preference').textContent).toBe('dark')
  })

  it('migrates a legacy "system" preference to a concrete default without crashing', () => {
    mockMatchMedia(true) // OS prefers dark
    window.localStorage.setItem('tradelens.theme', 'system')

    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    )

    // Migrated to a real value derived from the OS preference at migration time.
    expect(screen.getByTestId('preference').textContent).toBe('dark')
    expect(document.documentElement.getAttribute('data-theme')).toBe('dark')
  })

  it('migrates an unrecognized stored value to a concrete default without crashing', () => {
    window.localStorage.setItem('tradelens.theme', 'garbage-value')

    render(
      <ThemeProvider>
        <Probe />
      </ThemeProvider>,
    )

    expect(['light', 'dark']).toContain(screen.getByTestId('preference').textContent)
  })
})
