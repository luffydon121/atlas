import { expect, test } from "@playwright/test";

// Run against a read-only build: ATLAS_BASE_URL=... npx playwright test --project=demo
const OPEN = ["/", "/impact", "/briefing", "/markets", "/chart?s=AAPL", "/company?t=AAPL", "/crypto", "/economy", "/calendar", "/map", "/weather", "/transport", "/geopolitics", "/alternative", "/quality", "/sources"];

for (const path of OPEN) {
  test(`${path} works with no blocked requests`, async ({ page }) => {
    const blocked: string[] = [];
    page.on("response", (r) => { if (r.url().includes("/api/") && r.status() === 403) blocked.push(r.url()); });
    await page.goto(path);
    await expect(page.getByText("Public demo.")).toBeVisible();
    await page.waitForTimeout(1500);
    expect(blocked).toEqual([]);
  });
}

test("personal tools are hidden", async ({ page }) => {
  await page.goto("/chart?s=AAPL");
  await expect(page.getByRole("button", { name: "Assistant" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Notifications" })).toHaveCount(0);
  await expect(page.getByRole("button", { name: "Alert" })).toHaveCount(0);
  await expect(page.getByRole("link", { name: "Research", exact: true })).toHaveCount(0);
  await expect(page.getByRole("button", { name: /^Bitcoin|^S&P 500/ }).first()).toBeVisible({ timeout: 20_000 });
});

test("personal pages explain themselves", async ({ page }) => {
  for (const path of ["/portfolio", "/settings", "/events"]) {
    await page.goto(path);
    await expect(page.getByText("Available in the personal edition.")).toBeVisible();
  }
});
