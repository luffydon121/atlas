import { expect, test } from "@playwright/test";

test("tab bar and menu work", async ({ page }) => {
  await page.goto("/");
  const tabs = page.getByRole("navigation", { name: "Main" });
  await tabs.getByRole("link", { name: "Markets" }).tap();
  await expect(page).toHaveURL(/markets/);
  await page.getByRole("button", { name: "Open menu" }).tap();
  await page.getByRole("link", { name: "Satellite" }).first().tap();
  await expect(page).toHaveURL(/satellite/);
});

test("chart fills the screen above the watchlist", async ({ page }) => {
  await page.goto("/chart?s=AAPL");
  const chart = await page.locator(".chart-main").boundingBox();
  expect(chart!.width).toBeGreaterThan(340);
  expect(chart!.height).toBeGreaterThan(400);
});

test("map layers open as a sheet", async ({ page }) => {
  await page.goto("/map");
  await expect(page.getByText("Earthquakes")).toBeHidden();
  await page.getByRole("button", { name: "Layers" }).tap();
  await expect(page.getByText("Earthquakes")).toBeVisible();
});

test("workspace stacks", async ({ page }) => {
  await page.goto("/workspace");
  await expect(page.getByRole("textbox", { name: "Add symbol" })).toBeVisible({ timeout: 15_000 });
  await expect(page.locator("[data-separator]")).toHaveCount(0);
});
