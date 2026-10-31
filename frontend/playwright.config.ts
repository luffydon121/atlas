import { defineConfig, devices } from "@playwright/test";

export default defineConfig({
  testDir: "e2e",
  timeout: 60_000,
  retries: 1,
  use: { baseURL: process.env.ATLAS_BASE_URL ?? "http://127.0.0.1:3000" },
  projects: [
    { name: "chrome", testIgnore: /phone|demo/, use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "safari", testMatch: /smoke|v3/, use: { ...devices["Desktop Safari"], viewport: { width: 1440, height: 900 } } },
    { name: "demo", testMatch: /demo/, use: { ...devices["Desktop Chrome"], viewport: { width: 1440, height: 900 } } },
    { name: "iphone", testMatch: /phone/, use: devices["iPhone 14"] },
    { name: "android", testMatch: /phone/, use: devices["Pixel 7"] },
  ],
});
