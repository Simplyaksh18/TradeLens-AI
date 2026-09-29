import '@testing-library/jest-dom/vitest'

// jsdom does not implement matchMedia. Provide a default "light, no
// listeners fire" stub so ThemeProvider works in any test that doesn't
// explicitly mock it (tests that need to control system-theme behavior
// still override window.matchMedia themselves).
if (!window.matchMedia) {
  window.matchMedia = ((query: string) => ({
    matches: false,
    media: query,
    onchange: null,
    addEventListener: () => {},
    removeEventListener: () => {},
    addListener: () => {},
    removeListener: () => {},
    dispatchEvent: () => false,
  })) as unknown as typeof window.matchMedia
}
