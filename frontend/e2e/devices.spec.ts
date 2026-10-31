import { expect, test } from "@playwright/test";

const PAGES = ["/", "/impact", "/briefing", "/holdings", "/events", "/quality", "/markets", "/chart?s=AAPL", "/company?t=AAPL", "/company?t=BHP.AX", "/crypto", "/workspace", "/economy", "/calendar", "/map", "/satellite", "/weather", "/transport", "/geopolitics", "/alternative", "/quant", "/portfolio", "/alerts", "/sources", "/settings"];
const SIZES = { "small phone": [320, 640], phone: [390, 844], "phone landscape": [844, 390], tablet: [768, 1024], "tablet landscape": [1024, 768], laptop: [1280, 800], desktop: [1920, 1080], ultrawide: [2560, 1440] };

for (const [name, [width, height]] of Object.entries(SIZES)) {
  test.describe(name, () => {
    test.use({ viewport: { width, height } });
    test("no page scrolls sideways", async ({ page }) => {
      test.setTimeout(120_000);
      for (const path of PAGES) {
        await page.goto(path, { waitUntil: "domcontentloaded" });
        await page.waitForTimeout(500);
        const wide = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
        expect(wide, path).toBeLessThanOrEqual(1);
      }
    });
  });
}
