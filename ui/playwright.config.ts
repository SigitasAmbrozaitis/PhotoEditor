import { defineConfig } from '@playwright/test'

// End-to-end smoke test against the real backend serving the built UI (run `npm run build` first).
// Uses the installed Google Chrome (fresh temporary profile), so no Playwright browser download is needed.
const PORT = 8767

export default defineConfig({
  testDir: './e2e',
  outputDir: '../output/playwright',
  timeout: 60_000,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    channel: 'chrome',
    viewport: { width: 1440, height: 900 },
    colorScheme: 'dark',
  },
  webServer: {
    command: `uv run --project .. photoedit ui --no-browser --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 60_000,
  },
})
