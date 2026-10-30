/**
 * Real-browser end-to-end flows (review M-3; 13_ sections 5 and 7): Chromium against the real service and a
 * synthetic device database registered in the alpha's own configuration (setup.ts; issue #82: no import). Covers
 * the token hand-over, the default range, query, selection (UI-037), a failed request
 * keeping the last valid data with a working retry (R-1-5), that the ECharts spectrum actually paints pixels,
 * and that requests not addressed as 127.0.0.1 are refused (13_ 3.2).
 */
import { expect, test, type Page } from "@playwright/test";

const base = () => process.env.PAR_E2E_BASE_URL ?? "";
const token = () => process.env.PAR_E2E_TOKEN ?? "";

const ACQUISITIONS = "**/api/v0/devices/*/acquisitions*";

async function openPage(page: Page): Promise<void> {
  await page.goto(`${base()}/#token=${encodeURIComponent(token())}`);
  await expect(page.getByText("V2.0 试用版", { exact: false })).toBeVisible();
}

/** p1 is the registered synthetic device (setup.ts). */
async function deviceShown(page: Page): Promise<void> {
  await expect(page.locator('button.device[data-key="p1"]')).toBeEnabled({ timeout: 20_000 });
}

/** How many pixels the spectrum canvas actually painted (0 for a missing, empty or blank canvas). */
function paintedPixels(page: Page): Promise<number> {
  return page.evaluate(() => {
    const canvas = document.querySelector('[data-testid="spectrum-chart"] canvas') as HTMLCanvasElement | null;
    const context = canvas && canvas.width > 0 ? canvas.getContext("2d") : null;
    if (!canvas || !context) return 0;
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    let painted = 0;
    for (let index = 3; index < pixels.length; index += 4) if (pixels[index] !== 0) painted += 1;
    return painted;
  });
}

test("打开、查询、选择：记录表、光谱图与详情在真实浏览器中联动（不需导入，#82）", async ({ page }) => {
  await openPage(page);
  // the token travels as a fragment only and is stripped from the address bar at once
  await expect.poll(() => page.url()).not.toContain("token=");
  await deviceShown(page);
  await expect(page.getByText("历史库快照")).toHaveCount(0); // no snapshot panel any more (#82)

  // UI-049: the default range covers the device's own records (the synthetic day)
  const rows = page.locator("table.records tbody tr");
  const start = page.locator('input[name="start"]');
  await expect(start).toHaveValue("2026-10-01T00:00", { timeout: 20_000 });
  await expect(rows.first()).toBeVisible({ timeout: 20_000 });
  await expect(page.locator("table.records tbody tr.selected")).toHaveCount(1);

  // the spectrum is really rendered: a live ECharts instance whose canvas painted pixels
  const host = page.getByTestId("spectrum-chart");
  await expect(host).toHaveAttribute("_echarts_instance_", /.+/);
  await expect.poll(() => paintedPixels(page), { timeout: 15_000 }).toBeGreaterThan(1_000);

  // UI-049: the edited range takes effect on 查询 only; 30-minute records leave 5 rows in a 2-hour window.
  // No seconds: the browser drops ":00" seconds from a datetime-local value (the store fills them in).
  await page.fill('input[name="start"]', "2026-10-01T08:00");
  await page.fill('input[name="end"]', "2026-10-01T10:00");
  await page.getByRole("button", { name: "查询" }).click();
  await expect(rows).toHaveCount(5);

  // UI-037: picking another record moves the selection, the detail and the spectrum together
  const target = rows.nth(1);
  const id = await target.getAttribute("data-id");
  await target.click();
  await expect(target).toHaveClass(/selected/);
  await expect(page.locator('[aria-label="记录详情"] h2')).toContainText(`#${id}`);
});

test("查询失败时保留上次结果并可重试（R-1-5）", async ({ page }) => {
  await openPage(page);
  await deviceShown(page);
  const rows = page.locator("table.records tbody tr");
  await expect(rows.first()).toBeVisible({ timeout: 20_000 });
  const shown = await rows.count();

  await page.route(ACQUISITIONS, (route) => route.abort());
  await page.getByRole("button", { name: "查询" }).click();
  const notice = page.getByRole("alert").filter({ hasText: "仍显示上次查询结果" });
  await expect(notice).toBeVisible();
  await expect(rows).toHaveCount(shown); // the last valid list is kept on screen

  await page.unroute(ACQUISITIONS);
  await notice.getByRole("button", { name: "重试" }).click();
  await expect(notice).toHaveCount(0);
  await expect(rows.first()).toBeVisible();
});

test("非 127.0.0.1 的请求被拒绝（Host/Origin 校验）", async ({ request }) => {
  const viaLocalhost = await request.get(`http://localhost:${process.env.PAR_E2E_PORT}/api/v0/health`);
  expect(viaLocalhost.status()).toBe(403);
  const crossOrigin = await request.get(`${base()}/api/v0/health`, { headers: { Origin: "http://evil.example" } });
  expect(crossOrigin.status()).toBe(403);
  const sameOrigin = await request.get(`${base()}/api/v0/health`);
  expect(sameOrigin.ok()).toBeTruthy();
});
