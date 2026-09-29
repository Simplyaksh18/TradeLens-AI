import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { defineConfig } from 'vitest/config'

// https://vite.dev/config/
export default defineConfig({
  plugins: [react(), tailwindcss()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./src/test/setup.ts'],
    css: true,
    // Default 5000ms is occasionally too tight for multi-field form-fill
    // tests under this sandbox's jsdom overhead; not a sign of a slow app.
    testTimeout: 10000,
  },
})
