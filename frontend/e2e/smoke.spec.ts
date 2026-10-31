import { expect, test } from "@playwright/test";

const PAGES = ["/", "/workspace", "/calendar", "/markets", "/chart?s=AAPL", "/company?t=AAPL", "/economy", "/crypto", "/map", "/satellite", "/weather", "/transport", "/geopolitics", "/alternative", "/quant", "/portfolio", "/alerts", "/sources", "/settings"];

for (const path of PAGES) {
  test(`loads ${path} without page errors`, async ({ page }) => {
    const errors: string[] = [];
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("Failed to load resource")) errors.push(m.text()); });
    await page.goto(path);
    await expect(page.getByRole("navigation", { name: "Modules" })).toBeVisible();
    await page.waitForTimeout(2500);
    expect(errors).toEqual([]);
  });
}

test("command palette finds a ticker", async ({ page }) => {
  await page.goto("/");
  await page.keyboard.press("Meta+k");
  await page.getByPlaceholder("Search any ticker, company or page").fill("apple");
  await expect(page.getByRole("button", { name: /^AAPL Apple EQUITY/ })).toBeVisible({ timeout: 15_000 });
});

test("candlestick chart renders", async ({ page }) => {
  await page.goto("/chart?s=AAPL");
  await expect(page.getByTestId("price-chart").locator("canvas").first()).toBeVisible({ timeout: 20_000 });
});

test("world map starts and draws live layers", async ({ page }) => {
  await page.goto("/map");
  await expect(page.getByTestId("world-map")).toHaveAttribute("data-ready", "true", { timeout: 20_000 });
  await expect(page.getByText("Earthquakes")).toBeVisible();
});

test("company page keeps statements and valuation readable", async ({ page }) => {
  await page.goto("/company?t=AAPL");
  const head = page.getByText("Financial statements");
  await expect(head).toBeVisible({ timeout: 20_000 });
  await expect(page.getByRole("cell", { name: "Revenue", exact: true })).toBeVisible();
  await page.getByRole("button", { name: "Run DCF" }).click();
  await expect(page.getByText("Estimated value per share")).toBeVisible({ timeout: 20_000 });
});

test("portfolio and paper trading work end to end", async ({ page, request }) => {
  const name = `E2E ${Date.now()}`;
  const made = await (await request.post("/api/portfolios", { data: { name, kind: "paper", starting_cash: 100000, base_currency: "USD" } })).json();
  const fill = await request.post(`/api/portfolios/${made.id}/paper-order`, { data: { symbol: "AAPL", side: "buy", quantity: 2 } });
  expect(fill.status()).toBe(201);
  await page.goto("/portfolio");
  await page.getByLabel("Portfolio", { exact: true }).selectOption(String(made.id));
  await expect(page.getByRole("cell", { name: /^AAPL/ }).first()).toBeVisible({ timeout: 20_000 });
  await request.delete(`/api/portfolios/${made.id}`);
});

test("theme switch changes the page", async ({ page }) => {
  await page.goto("/");
  const before = await page.evaluate(() => document.documentElement.dataset.theme);
  await page.getByRole("button", { name: "Switch theme" }).click();
  expect(await page.evaluate(() => document.documentElement.dataset.theme)).not.toBe(before);
});

test("today shows a briefing with sparklines", async ({ page }) => {
  await page.goto("/");
  await expect(page.locator(".today-hero h1")).toContainText(/%|unavailable/, { timeout: 20_000 });
  await expect(page.locator(".market-tile polyline").first()).toBeVisible({ timeout: 20_000 });
});

test("menu flyout opens and navigates", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("link", { name: "World", exact: true }).hover();
  await page.getByRole("link", { name: /Satellite/ }).first().click();
  await expect(page).toHaveURL(/satellite/);
});

test("repeat visits with remembered data render one headline", async ({ page }) => {
  const errors: string[] = [];
  page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("Failed to load resource")) errors.push(m.text()); });
  await page.goto("/economy");
  await page.waitForTimeout(1500);
  await page.goto("/");
  await page.waitForTimeout(1500);
  await page.goto("/markets");
  await page.waitForTimeout(1500);
  await page.goto("/crypto");
  await page.waitForTimeout(1500);
  await expect(page.locator(".hero")).toHaveCount(1);
  expect(errors).toEqual([]);
});

test.describe("dark theme", () => {
  test.use({ colorScheme: "dark" });

  for (const path of ["/markets", "/economy", "/crypto", "/calendar", "/sources"]) {
    test(`renders one headline on ${path}`, async ({ page }) => {
      const errors: string[] = [];
      page.on("console", (m) => { if (m.type() === "error" && !m.text().includes("Failed to load resource")) errors.push(m.text()); });
      await page.addInitScript(() => localStorage.setItem("atlas-theme", "dark"));
      await page.goto(path);
      await page.waitForTimeout(1200);
      await expect(page.locator(".hero")).toHaveCount(1);
      expect(await page.evaluate(() => document.documentElement.dataset.theme)).toBe("dark");
      expect(errors).toEqual([]);
    });
  }
});
