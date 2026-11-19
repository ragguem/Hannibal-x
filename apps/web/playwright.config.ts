import { defineConfig, devices } from "@playwright/test";

// The e2e run uses the in-browser fake API (MSW, `vite --mode mock`): no back-office, no LOTUSim.
export default defineConfig({
  testDir: "./e2e",
  timeout: 60_000,
  fullyParallel: false,
  forbidOnly: true,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: "http://127.0.0.1:5174",
    trace: "retain-on-failure",
    locale: "fr-FR",
  },
  // HX_E2E_CHANNEL=msedge (or chrome) reuses an installed browser instead of `playwright install`.
  projects: [{ name: "chromium", use: { ...devices["Desktop Chrome"], channel: process.env.HX_E2E_CHANNEL } }],
  webServer: {
    command: "pnpm exec vite --mode mock --port 5174 --strictPort --host 127.0.0.1",
    url: "http://127.0.0.1:5174",
    reuseExistingServer: false,
    timeout: 60_000,
  },
});
