import { defineConfig, devices } from "@playwright/test";

// Runs against the Vite dev server in fixture mode: no backend or pipeline needed.
// PW_CHANNEL=msedge (or chrome) uses an installed browser instead of Playwright's Chromium download.
const PORT = 5174;
const channel = process.env.PW_CHANNEL;

export default defineConfig({
  testDir: "e2e",
  timeout: 30_000,
  retries: process.env.CI ? 1 : 0,
  reporter: [["list"]],
  use: {
    baseURL: `http://localhost:${PORT}`,
    trace: "retain-on-failure",
  },
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], ...(channel ? { channel } : {}) } }],
  webServer: {
    command: `npm run dev:fixtures -- --port ${PORT} --strictPort`,
    url: `http://localhost:${PORT}/pipelines`,
    reuseExistingServer: !process.env.CI,
    timeout: 60_000,
  },
});
