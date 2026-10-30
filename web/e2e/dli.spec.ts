/**
 * DLI page in a real browser (review of PR #47, M-3; 13_ sections 5 and 7): Chromium against the real service
 * and a synthetic device database with one-minute records (p3 光积累 of setup.ts; p1 and p2 belong to the
 * calculation and export e2e). Covers that the four ECharts charts
 * actually paint their curves, that a picked date is applied on 查看, that a failed request keeps the shown period
 * with a working retry (R-1-5), and that the picker's limit passes Beijing midnight while a finished period stays
 * on screen without reloading (review M-1).
 */
import { expect, test, type Page } from "@playwright/test";

const base = () => process.env.PAR_E2E_BASE_URL ?? "";
const token = () => process.env.PAR_E2E_TOKEN ?? "";

const DLI = "**/api/v0/devices/*/dli*";
const DAY = "2026-10-01"; // the synthetic day: records every minute, DLI enabled at 00:00

async function openDli(page: Page): Promise<void> {
  await page.goto(`${base()}/#token=${encodeURIComponent(token())}`);
  await expect(page.getByText("V2.0 试用版", { exact: false })).toBeVisible();
  const device = page.locator('button.device[data-key="p3"]');
  await expect(device).toBeEnabled({ timeout: 20_000 });
  await device.click();
  await page.getByRole("navigation", { name: "主导航" }).getByRole("button", { name: "光积累计算" }).click();
  await expect(page.locator(".dli-chart")).toHaveCount(4, { timeout: 20_000 });
}

async function pickDate(page: Page, date: string): Promise<void> {
  await page.getByLabel("周期日期").fill(date);
  await page.getByRole("button", { name: "查看", exact: true }).click();
}

/** Painted (non-transparent) pixels of each DLI chart canvas, in page order. */
function paintedPixels(page: Page): Promise<number[]> {
  return page.evaluate(() =>
    [...document.querySelectorAll('[data-testid="dli-chart"]')].map((host) => {
      const canvas = host.querySelector("canvas");
      const context = canvas && canvas.width > 0 ? canvas.getContext("2d") : null;
      if (!canvas || !context) return 0;
      const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
      let painted = 0;
      for (let index = 3; index < pixels.length; index += 4) if (pixels[index] !== 0) painted += 1;
      return painted;
    }),
  );
}

test("DLI：选日期查看，四图在真实浏览器中绘出累计曲线", async ({ page }) => {
  await openDli(page);
  const axesOnly = await (async () => {
    // a period without records draws axes only: the baseline the curves must exceed
    await pickDate(page, "2026-10-05");
    await expect(page.locator('[data-role="period"]')).toContainText("2026-10-05");
    await expect(page.locator(".dli-chart .no-data")).toHaveCount(4);
    await expect.poll(async () => Math.min(...(await paintedPixels(page)))).toBeGreaterThan(0);
    return Math.max(...(await paintedPixels(page)));
  })();

  await pickDate(page, DAY);
  await expect(page.locator('[data-role="period"]')).toContainText(`${DAY} `);
  await expect(page.locator(".badge")).toHaveText("已结束的周期");
  await expect(page.locator(".dli-chart .no-data")).toHaveCount(0);
  for (const total of await page.locator(".dli-chart .total").allTextContents()) expect(total).toMatch(/\d\.\d{3}/);
  const charts = page.getByTestId("dli-chart");
  for (const chart of await charts.all()) await expect(chart).toHaveAttribute("_echarts_instance_", /.+/);
  // every chart paints its filled curve on top of the axes
  await expect
    .poll(async () => Math.min(...(await paintedPixels(page))), { timeout: 15_000 })
    .toBeGreaterThan(axesOnly + 1_000);
});

test("DLI：读取失败时保留所示周期并可重试（R-1-5）", async ({ page }) => {
  await openDli(page);
  await pickDate(page, DAY);
  const period = page.locator('[data-role="period"]');
  await expect(period).toContainText(`${DAY} `);

  await page.route(DLI, (route) => route.abort());
  await pickDate(page, "2026-10-02");
  const notice = page.getByRole("alert").filter({ hasText: "仍显示上次读取的结果" });
  await expect(notice).toBeVisible();
  await expect(notice).toContainText("所选日期 2026-10-02 的周期尚未读取成功");
  await expect(period).toContainText(`${DAY} `); // the last valid period stays on screen
  await expect(page.locator(".dli-chart")).toHaveCount(4);

  await page.unroute(DLI);
  await notice.getByRole("button", { name: "重试" }).click();
  await expect(notice).toHaveCount(0);
  await expect(period).toContainText("2026-10-02 ");
});

test("DLI：查看已结束周期时，日期上限随北京时间跨日更新（M-1）", async ({ page }) => {
  // The service's clock cannot be moved: its answer gets as_of 23:59:30 of DAY, and the page's clock is advanced.
  await page.clock.install();
  let requests = 0;
  await page.route(DLI, async (route) => {
    requests += 1;
    const response = await route.fetch();
    const body = { ...(await response.json()), as_of: `${DAY}T23:59:30.000` };
    await route.fulfill({ response, json: body });
  });
  await openDli(page);
  await pickDate(page, "2026-09-30");
  await expect(page.locator(".badge")).toHaveText("已结束的周期");
  const picker = page.getByLabel("周期日期");
  await expect(picker).toHaveAttribute("max", DAY);
  const before = requests;

  await page.clock.runFor(60_000);
  await expect(picker).toHaveAttribute("max", "2026-10-02");
  expect(requests).toBe(before); // a finished period is still not reloaded
  await pickDate(page, "2026-10-02");
  await expect(page.locator('[data-role="period"]')).toContainText("2026-10-02 ");
});

test("DLI：保存经纬度并重置周期，按新位置重算周期，再改回北京（issue 116）", async ({ page }) => {
  await openDli(page);
  const period = page.locator("[data-role=period]");
  const before = (await period.textContent()) ?? "";
  await page.getByLabel("纬度（°N）").fill("31.2304");
  await page.getByLabel("经度（°E）").fill("121.4737");
  await expect(period).toHaveText(before); // DLI-025: typing alone does not apply
  const saved = page.waitForResponse((response) => response.url().includes("/dli/location") && response.ok());
  await page.getByRole("button", { name: "保存经纬度并重置周期" }).click();
  await saved;
  await expect(period).not.toHaveText(before);
  await expect(page.getByText("纬度 31.2304 °N，经度 121.4737 °E")).toBeVisible();
  await expect(page.getByText("（已保存）")).toBeVisible();
  // the shared e2e database goes back to the default place for the other tests
  await page.getByLabel("纬度（°N）").fill("39.9042");
  await page.getByLabel("经度（°E）").fill("116.4074");
  await page.getByRole("button", { name: "保存经纬度并重置周期" }).click();
  await expect(period).toHaveText(before);
});
