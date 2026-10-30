/**
 * Real-browser end-to-end tests (review M-3; 13_ sections 5 and 7): the built page on the real service with a
 * synthetic V1.0.x database, in Chromium. Run `npm run build` first; `e2e/setup.ts` starts (and stops) the service.
 * One worker, not parallel: the tests share that one service and its imported snapshot. In CI a failed test is
 * retried once (flaky-network allowance); locally a failure fails at once.
 */
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  globalSetup: "./e2e/setup.ts",
  fullyParallel: false,
  workers: 1,
  retries: process.env.CI ? 1 : 0,
  timeout: 60_000,
  reporter: [["list"]],
  use: { trace: "retain-on-failure", viewport: { width: 1440, height: 1000 } }, // the page asks for ≥1100 px width
});
