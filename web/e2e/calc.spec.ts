/**
 * Real-browser end-to-end flows of the spectrum calculation page (13_ sections 5 and 7): Chromium against the real
 * service with two synthetic device databases registered in the alpha's own configuration (setup.ts; issue #82) (p1, and p2 = the same light through a made-up cover 20 s later).
 * Covers the initial A/B choice and nearest-time match, that all three charts really paint, the ratio, the export
 * into the alpha's output folder (and that cancelling writes nothing), and that a failed request keeps the charts
 * with a working retry (R-1-5). With PAR_SCREENSHOT_DIR set it also writes calc-100.png and calc-150.png there
 * (1680×900, UI-224).
 */
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type Browser, type Page } from "@playwright/test";

const base = () => process.env.PAR_E2E_BASE_URL ?? "";
const token = () => process.env.PAR_E2E_TOKEN ?? "";
const INPUTS = "**/api/v0/operations/inputs";

async function openCalc(page: Page): Promise<void> {
  await page.goto(`${base()}/?view=calc#token=${encodeURIComponent(token())}`);
  await expect(page.getByRole("button", { name: "光谱计算" })).toHaveAttribute("aria-current", "page");
  await expect(page.getByTestId("time-difference")).toContainText("采集时间差", { timeout: 20_000 });
}

/** How many pixels the chart's canvas painted (0 for a missing, empty or blank canvas). */
function paintedPixels(page: Page, testId: string): Promise<number> {
  return page.evaluate((id) => {
    const canvas = document.querySelector(`[data-testid="${id}"] canvas`) as HTMLCanvasElement | null;
    const context = canvas && canvas.width > 0 ? canvas.getContext("2d") : null;
    if (!canvas || !context) return 0;
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    let painted = 0;
    for (let index = 3; index < pixels.length; index += 4) if (pixels[index] !== 0) painted += 1;
    return painted;
  }, testId);
}

function exportFolders(): string[] {
  const folder = join(process.env.PAR_E2E_DATA_DIR ?? "", "exports");
  return existsSync(folder) ? readdirSync(folder) : [];
}

test("光谱计算：初始 A/B、最近时间匹配、比值计算与三图渲染", async ({ page }) => {
  await openCalc(page);
  // UI-156: A = first source, B = second; UI-201: B is matched to A's time on the first visit
  await expect(page.getByTestId("a-source")).toHaveValue("p1");
  await expect(page.getByTestId("b-source")).toHaveValue("p2");
  await expect(page.getByTestId("time-difference")).toHaveText("采集时间差：B 比 A 晚 20.000 秒");
  await expect(page.getByTestId("chart-result-empty")).toContainText("等待执行计算");
  for (const id of ["chart-a", "chart-b"]) {
    await expect.poll(() => paintedPixels(page, id), { timeout: 15_000 }).toBeGreaterThan(1_000);
  }

  // pick a midday record of A: B follows to the record 20 s later (UI-163)
  const middayA = page.getByTestId("a-record").locator("option", { hasText: "12:00:00.000" });
  await page.getByTestId("a-record").selectOption({ value: (await middayA.getAttribute("value")) ?? "" });
  await expect(page.getByTestId("b-record")).toContainText("12:00:20.000");
  await page.getByTestId("operation").selectOption("divide");
  const waiting = await paintedPixels(page, "chart-result"); // axes and grid only (UI-212: no y labels)
  await page.getByTestId("run").click();
  await expect(page.getByTestId("chart-result-title")).toHaveText("计算结果：比值 A/B");
  await expect(page.getByText("比值显示：A、B 均达到两条光谱最大峰值的 2%。")).toBeVisible();
  // the ratio curve itself is painted: clearly more pixels than the empty axes
  await expect.poll(() => paintedPixels(page, "chart-result"), { timeout: 15_000 }).toBeGreaterThan(waiting + 500);

  // UI-158: changing the operation drops the result
  await page.getByTestId("operation").selectOption("add");
  await expect(page.getByTestId("chart-result-empty")).toContainText("等待执行计算");
  await expect(page.getByTestId("export")).toBeDisabled();
});

test("导出计算结果：取消不写文件，确认后在输出目录新建结果目录（EXP-021、EXP-024、D-207）", async ({ page }) => {
  await openCalc(page);
  await page.getByTestId("run").click();
  await expect(page.getByTestId("export")).toBeEnabled();
  const before = exportFolders();

  await page.getByTestId("export").click();
  await page.getByRole("button", { name: "取消" }).click();
  expect(exportFolders()).toEqual(before);

  await page.getByTestId("export").click();
  await page.getByLabel("Excel (.xlsx)").check();
  await page.getByRole("button", { name: "导出到输出目录" }).click();
  await expect(page.getByTestId("export-done")).toContainText("已保存 2 个文件");
  const created = exportFolders().filter((name) => !before.includes(name));
  expect(created).toHaveLength(1);
  const files = readdirSync(join(process.env.PAR_E2E_DATA_DIR ?? "", "exports", created[0] ?? "")).sort();
  expect(files).toHaveLength(2);
  expect(files[0]).toMatch(/^A\d+_add_B\d+\.csv$/);
  expect(files[1]).toMatch(/^A\d+_add_B\d+\.xlsx$/);
});

test("光谱计算：读取失败时保留两图并可重试（R-1-5）", async ({ page }) => {
  await openCalc(page);
  await expect.poll(() => paintedPixels(page, "chart-a"), { timeout: 15_000 }).toBeGreaterThan(1_000);
  const title = await page.getByTestId("chart-a-title").textContent();

  await page.route(INPUTS, (route) => route.abort());
  await page.getByTestId("swap").click();
  const notice = page.getByRole("alert").filter({ hasText: "仍显示上次读取的光谱" });
  await expect(notice).toBeVisible();
  await expect(page.getByTestId("chart-a-title")).toHaveText(title ?? "");
  await expect(page.getByTestId("run")).toBeDisabled(); // the charts no longer match the selection

  await page.unroute(INPUTS);
  await notice.getByRole("button", { name: "重试" }).click();
  await expect(notice).toHaveCount(0);
  await expect(page.getByTestId("chart-a-title")).toContainText("温室内");
  await expect(page.getByTestId("run")).toBeEnabled();
});

async function screenshot(browser: Browser, scale: number, folder: string): Promise<void> {
  const context = await browser.newContext({ viewport: { width: 1680, height: 900 }, deviceScaleFactor: scale });
  const page = await context.newPage();
  await openCalc(page);
  const midday = page.getByTestId("a-record").locator("option", { hasText: "12:00:00.000" });
  await page.getByTestId("a-record").selectOption({ value: (await midday.getAttribute("value")) ?? "" });
  await expect(page.getByTestId("b-record")).toContainText("12:00:20.000");
  await page.getByTestId("swap").click(); // A = inside (with the cover), B = outside, as the guide's greenhouse case
  await expect(page.getByTestId("chart-a-title")).toContainText("温室内");
  await page.getByTestId("operation").selectOption("divide");
  const waiting = await paintedPixels(page, "chart-result"); // axes and grid only
  await page.getByTestId("run").click();
  await expect(page.getByTestId("chart-result-title")).toHaveText("计算结果：比值 A/B");
  await expect.poll(() => paintedPixels(page, "chart-result"), { timeout: 15_000 }).toBeGreaterThan(waiting + 500);
  await page.screenshot({ path: join(folder, `calc-${Math.round(scale * 100)}.png`) });
  await context.close();
}

test("截图：1680×900，100% 与 150%（只在设置 PAR_SCREENSHOT_DIR 时运行）", async ({ browser }) => {
  const folder = process.env.PAR_SCREENSHOT_DIR;
  test.skip(!folder, "PAR_SCREENSHOT_DIR is not set");
  for (const scale of [1, 1.5]) await screenshot(browser, scale, folder ?? "");
});
