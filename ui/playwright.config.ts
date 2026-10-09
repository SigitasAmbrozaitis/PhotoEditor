import { defineConfig } from '@playwright/test'

// End-to-end smoke test against the real backend serving the built UI (run `npm run build` first).
// Uses the installed Google Chrome (fresh temporary profile), so no Playwright browser download is needed.
// scripts/e2e_setup.py first writes synthetic photos to output/e2e/; the server's workspace, cache and suggested
// folder and styles point there, so the test never sees the real catalog, styles or photos.
const PORT = 8767
const E2E = 'output/e2e' // relative to the project root, like every PHOTOEDIT_* path

export default defineConfig({
  testDir: './e2e',
  outputDir: '../output/playwright',
  timeout: 60_000,
  workers: 1, // the tests share one server and build on each other's import
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    channel: 'chrome',
    viewport: { width: 1440, height: 900 },
    colorScheme: 'dark',
  },
  webServer: {
    command:
      `uv run --project .. python ../scripts/e2e_setup.py && ` +
      `uv run --project .. photoedit ui --no-browser --port ${PORT}`,
    url: `http://127.0.0.1:${PORT}/api/health`,
    reuseExistingServer: false,
    timeout: 120_000,
    env: {
      PHOTOEDIT_WORKSPACE_DIR: `${E2E}/workspace`,
      PHOTOEDIT_CACHE_DIR: `${E2E}/cache`,
      PHOTOEDIT_STYLES_DIR: `${E2E}/styles`,
      PHOTOEDIT_SAMPLE_PHOTOS_DIR: `${E2E}/photos`,
    },
  },
})
