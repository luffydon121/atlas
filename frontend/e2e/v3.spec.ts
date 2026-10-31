import AxeBuilder from "@axe-core/playwright";
import { expect, test } from "@playwright/test";

for (const path of ["/", "/impact", "/briefing", "/quality", "/markets", "/economy", "/transport"]) {
  test(`no serious accessibility problems on ${path}`, async ({ page }) => {
    await page.goto(path);
    await page.waitForTimeout(2000);
    const results = await new AxeBuilder({ page }).analyze();
    const serious = results.violations.filter((v) => v.impact === "serious" || v.impact === "critical");
    expect(serious.map((v) => `${v.id}: ${v.nodes.length} ${v.nodes.slice(0, 3).map((n) => `${n.target} ${(n.any[0]?.data as { contrastRatio?: number; fgColor?: string; bgColor?: string } | undefined)?.fgColor}/${(n.any[0]?.data as { bgColor?: string } | undefined)?.bgColor}`).join(" | ")}`)).toEqual([]);
  });
}


test("impact engine shows events, exposure and evidence", async ({ page }) => {
  await page.goto("/impact");
  await expect(page.getByText("Event feed")).toBeVisible();
  await expect(page.locator(".feed-item").first()).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Possible exposure")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByText("Hypothetical", { exact: true })).toBeVisible();
  await expect(page.getByText("Evidence", { exact: true })).toBeVisible();
});

test("scenario mode is clearly hypothetical", async ({ page }) => {
  await page.goto("/impact");
  await page.getByRole("button", { name: "Scenario" }).click();
  await expect(page.getByText("This is a hypothetical scenario, not a live event.")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByRole("link", { name: "XOM" }).first()).toBeVisible();
  await expect(page.getByText("What happened around similar past events")).toBeVisible();
  await expect(page.getByRole("cell", { name: "CL=F" }).first()).toBeVisible({ timeout: 40_000 });
});

test("event study measures real history", async ({ page }) => {
  await page.goto("/events");
  await expect(page.getByLabel("Event set").locator("option").first()).toBeAttached({ timeout: 15_000 });
  await page.getByRole("button", { name: "Run study" }).click();
  await expect(page.getByText("Events measured")).toBeVisible({ timeout: 30_000 });
});

test("data quality center lists sources and jobs", async ({ page }) => {
  await page.goto("/quality");
  await expect(page.getByRole("cell", { name: /Yahoo Finance/ })).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Personal use. Do not republish.")).toBeVisible();
  await expect(page.getByText("Background jobs")).toBeVisible();
});

test("a briefing can be generated and states its coverage", async ({ page }) => {
  await page.goto("/briefing");
  await page.getByRole("button", { name: "Country" }).click();
  await page.getByLabel("Subject").fill("Australia");
  await page.getByRole("button", { name: "Generate" }).click();
  await expect(page.getByText("Period covered")).toBeVisible({ timeout: 30_000 });
  await expect(page.getByRole("heading", { name: "Unavailable feeds" })).toBeVisible();
});

test("holdings explain what is missing without a contact", async ({ page }) => {
  await page.goto("/holdings");
  await expect(page.getByText(/filing history/)).toBeVisible({ timeout: 20_000 });
});

test("a satellite area can be drawn and saved", async ({ page }) => {
  await page.goto("/satellite");
  const map = page.getByTestId("area-map");
  await expect(map.locator("canvas")).toBeVisible({ timeout: 20_000 });
  await map.scrollIntoViewIfNeeded();
  await page.waitForTimeout(2500);
  const box = (await map.boundingBox())!;
  for (const [x, y] of [[0.5, 0.45], [0.504, 0.45], [0.504, 0.455]]) await page.mouse.click(box.x + box.width * x, box.y + box.height * y);
  await expect(page.getByRole("button", { name: "Undo" })).toBeEnabled();
  const name = `Test area ${Date.now()}`;
  await page.getByLabel("Area name").fill(name);
  await page.getByRole("button", { name: "Save area" }).click();
  const row = page.getByRole("row", { name });
  await expect(row).toBeVisible({ timeout: 10_000 });
  await row.getByRole("button", { name: "Delete" }).click();
  await expect(page.getByRole("row", { name: name })).toHaveCount(0);
});

test("map shows the impact layer and clusters", async ({ page }) => {
  await page.goto("/map");
  await expect(page.getByTestId("world-map")).toHaveAttribute("data-ready", "true", { timeout: 20_000 });
  await page.getByLabel(/Impact Engine events/).check({ force: true });
  await page.waitForTimeout(800);
  await expect(page.getByText("Saved views")).toBeVisible();
});

test("trade page lists ports", async ({ page }) => {
  await page.goto("/transport");
  await expect(page.getByText("Major ports")).toBeVisible();
  await expect(page.getByRole("cell", { name: /Shanghai/ })).toBeVisible({ timeout: 15_000 });
});
