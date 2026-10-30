/**
 * Real-browser end-to-end flows of the overview (实时概览; D-211, D-214; issue #82): Chromium against the real
 * service in tier 1, not taken over, with the synthetic device databases of setup.ts registered in its own
 * configuration (records every 30 minutes on 2026-10-01). Covers the "not acquiring" banner, the six cards and the
 * status line as the service wrote them, "全部指标" of the live record (issue #106, as V1.0.3), "显示指标" (UI-061),
 * that the spectrum paints, and that a failed reload keeps the shown overview with a working retry (R-1-5). The
 * takeover itself is takeover.spec.ts. With PAR_SCREENSHOT_DIR set it also writes overview-100.png and
 * overview-150.png there (1680×900).
 */
import { join } from "node:path";
import { expect, test, type APIRequestContext, type Browser, type Page } from "@playwright/test";

const base = () => process.env.PAR_E2E_BASE_URL ?? "";
const token = () => process.env.PAR_E2E_TOKEN ?? "";
const LATEST = "**/api/v0/acquisition/devices/*/latest";
/** The name the e2e scratch folder starts with (setup.ts); no screenshot may show it (R-4-7). */
const SCRATCH = "par-e2e-";

interface OverviewBody {
  status: { text: string };
  kpis: { title: string; text: string }[];
  display_record: { id: number; details_title: string } | null;
}

async function serviceOverview(request: APIRequestContext): Promise<OverviewBody> {
  const response = await request.get(`${base()}/api/v0/acquisition/devices/p1/latest`, {
    headers: { "X-PAR-Token": token() },
  });
  expect(response.status()).toBe(200);
  return (await response.json()) as OverviewBody;
}

async function openOverview(page: Page): Promise<void> {
  await page.goto(`${base()}/?view=overview#token=${encodeURIComponent(token())}`);
  await expect(page.getByRole("button", { name: "实时概览" })).toHaveAttribute("aria-current", "page");
  await expect(page.locator("[data-role=status]")).toContainText("显示 #", { timeout: 20_000 });
}

function paintedPixels(page: Page): Promise<number> {
  return page.evaluate(() => {
    const canvas = document.querySelector('[data-testid="overview-chart"] canvas') as HTMLCanvasElement | null;
    if (!canvas || canvas.width === 0 || canvas.height === 0) return 0;
    const data = canvas.getContext("2d")?.getImageData(0, 0, canvas.width, canvas.height).data;
    if (!data) return 0;
    let painted = 0;
    for (let index = 3; index < data.length; index += 4) if ((data[index] ?? 0) > 0) painted += 1;
    return painted;
  });
}

test("实时概览：未在采集的标注、摘要卡与状态行同服务（档位 1，#82）", async ({ page }) => {
  await openOverview(page);
  const body = await serviceOverview(page.request);
  await expect(page.locator("[data-role=live-banner]")).toHaveText("未在采集：显示设备库中的最后数据");
  await expect(page.locator("[data-role=kpis] .label")).toHaveText(body.kpis.map((kpi) => kpi.title));
  await expect(page.locator("[data-role=kpis] .value")).toHaveText(body.kpis.map((kpi) => kpi.text));
  // the records end on 2026-10-01: the age keeps moving, so compare up to "距今"
  const head = body.status.text.slice(0, body.status.text.indexOf("距今"));
  await expect(page.locator("[data-role=status]")).toContainText(head);
  await expect(page.getByRole("button", { name: "开始采集", exact: true })).toBeVisible(); // not taken over
  await expect.poll(() => paintedPixels(page)).toBeGreaterThan(1000);
});

test("实时概览：显示指标可关闭图内指标（UI-061）", async ({ page }) => {
  await openOverview(page);
  await expect(page.locator("[data-role=overlay] .row")).toHaveCount(20); // UI-060
  await page.getByLabel("显示指标").uncheck();
  await expect(page.locator("[data-role=overlay]")).toHaveCount(0);
  await page.getByLabel("显示指标").check();
  await expect(page.locator("[data-role=overlay] .row")).toHaveCount(20);
});

test("实时概览：实时记录的全部指标，标题与 54 项同服务（UI-009、UI-018，#106）", async ({ page }) => {
  await openOverview(page);
  const body = await serviceOverview(page.request);
  const shown = body.display_record;
  expect(shown).not.toBeNull();
  const button = page.locator("[data-role=details-button]");
  await expect(button).toBeEnabled();
  await button.click();
  const dialog = page.locator("[data-role=details-dialog]");
  await expect(dialog).toHaveAttribute("aria-label", shown?.details_title ?? "");
  await expect(dialog.locator("thead th")).toHaveText(["指标", "数值", "单位"]);
  await expect(dialog.locator("tr.group")).toHaveCount(7);
  await expect(dialog.locator("tbody tr[data-key]")).toHaveCount(54);
  await dialog.getByRole("button", { name: "关闭" }).click();
  await expect(dialog).toHaveCount(0);
});

test("实时概览：刷新失败时保留上次结果并可重试（R-1-5）", async ({ page }) => {
  await openOverview(page);
  const status = page.locator("[data-role=status]");
  const shown = (await status.textContent()) ?? "";
  const record = shown.slice(0, shown.indexOf("距今"));
  await page.route(LATEST, (route) => route.abort());
  const notice = page.getByRole("alert").filter({ hasText: "仍显示上次读取的 #" });
  await expect(notice).toBeVisible({ timeout: 10_000 }); // the 3-second reload fails
  await expect(status).toContainText(record);
  await page.unroute(LATEST);
  await notice.getByRole("button", { name: "重试" }).click();
  await expect(notice).toHaveCount(0);
  await expect(status).toContainText(record);
});

async function screenshot(browser: Browser, scale: number, folder: string): Promise<void> {
  const context = await browser.newContext({ viewport: { width: 1680, height: 900 }, deviceScaleFactor: scale });
  const page = await context.newPage();
  await openOverview(page);
  await expect.poll(() => paintedPixels(page)).toBeGreaterThan(1000);
  await expect(page.locator("body")).not.toContainText(SCRATCH);
  await page.screenshot({ path: join(folder, `overview-${Math.round(scale * 100)}.png`) });
  await context.close();
}

test("截图：1680×900，100% 与 150%（只在设置 PAR_SCREENSHOT_DIR 时运行）", async ({ browser }) => {
  const folder = process.env.PAR_SCREENSHOT_DIR;
  test.skip(!folder, "PAR_SCREENSHOT_DIR is not set");
  for (const scale of [1, 1.5]) await screenshot(browser, scale, folder ?? "");
});
