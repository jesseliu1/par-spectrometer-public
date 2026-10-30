/**
 * Real-browser end-to-end flows of the read-only settings page and the acquisition export (13_ sections 5 and 7):
 * Chromium against the real service with two synthetic device databases registered in the alpha's own configuration (setup.ts; issue #82) (records every 30 minutes on 2026-10-01).
 * Covers the device list of the alpha's own configuration in tier 1 (#82), the count of a preset and of a custom
 * range, the one confirmation (否 writes nothing, 是 writes device/format/date folders into the alpha's output
 * folder, D-210), that a failed count keeps the last one with a working retry (R-1-5), and V1.0.3's 设备状态与最近日志
 * in tier 1 (status line, log table, 日志详情; issue #107). With PAR_SCREENSHOT_DIR
 * set it also writes export-100.png and export-150.png there (1680×900, UI-224).
 */
import { existsSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { expect, test, type APIRequestContext, type Browser, type Page } from "@playwright/test";

const base = () => process.env.PAR_E2E_BASE_URL ?? "";
const token = () => process.env.PAR_E2E_TOKEN ?? "";
/** The name the e2e scratch folder starts with (setup.ts; the shown path may be the resolved /private/... one). */
const SCRATCH = "par-e2e-";
/** What the screenshots show instead of the scratch output folder. */
const NEUTRAL_DIRECTORY = "<alpha 数据目录>/exports";
const COUNT = "**/api/v0/devices/*/export/count*";
const DAY_START = "2026-10-01T00:00:00";
const DAY_END = "2026-10-01T23:59:59";

/** Records of p1 on 2026-10-01 as the service counts them (the page must show the same number). */
async function dayCount(request: APIRequestContext): Promise<number> {
  const params = new URLSearchParams({ range: "custom", start: DAY_START, end: DAY_END });
  const response = await request.get(`${base()}/api/v0/devices/p1/export/count?${params}`, {
    headers: { "X-PAR-Token": token() },
  });
  return ((await response.json()) as { count: number }).count;
}

async function openSettings(page: Page): Promise<void> {
  await page.goto(`${base()}/?view=settings#token=${encodeURIComponent(token())}`);
  await expect(page.getByRole("button", { name: "设置与导出" })).toHaveAttribute("aria-current", "page");
  await expect(page.locator("[data-role=count]")).toContainText("预计", { timeout: 20_000 });
}

async function customDay(page: Page): Promise<void> {
  await page.locator("select[name=export-range]").selectOption("custom");
  await page.locator("input[name=export-start]").fill(DAY_START.replace("T", " "));
  await page.locator("input[name=export-start]").dispatchEvent("change");
  await page.locator("input[name=export-end]").fill(DAY_END.replace("T", " "));
  await page.locator("input[name=export-end]").dispatchEvent("change");
}

function exported(kind: "CSV" | "Excel"): string[] {
  const folder = join(process.env.PAR_E2E_DATA_DIR ?? "", "exports", "温室外", kind, "2026-10-01");
  return existsSync(folder) ? readdirSync(folder).sort() : [];
}

test("设置与导出：导出设备与状态区来自 alpha 自己登记的设备（#82）", async ({ page }) => {
  await openSettings(page);
  const device = page.locator("select[name=export-device]");
  await expect(device.locator("option")).toHaveText(["温室外", "温室内", "光积累"]);
  // tier 1 without a takeover (setup.ts never starts acquiring): V1.0.3's status line says so (issue #107)
  await expect(page.locator("[data-role=status-line]")).toHaveText(/^温室外 · 未在采集：未连接设备$/);
  await expect(page.locator("[data-role=status]")).toContainText("最近采集");
  await expect(page.getByText("历史库快照")).toHaveCount(0);
});

test("设备状态与最近日志：设备库的日志、异常标红、双击看日志详情（UI-078、UI-100、UI-279，#107）", async ({ page }) => {
  await openSettings(page);
  const log = page.locator("[data-role=log]");
  await expect(log.locator("th")).toHaveText(["时间", "类别", "结果"]);
  const rows = log.locator("tbody tr");
  await expect(rows).toHaveCount(3);
  await expect(rows.nth(0).locator("td")).toHaveText(["2026-10-01 10:06:00.000", "通信恢复", "通信已恢复（演示数据）"]);
  await expect(rows.nth(1)).toHaveClass(/error/);
  await expect(rows.nth(1).locator("td").nth(2)).toHaveAttribute("title", "设备无应答（演示数据）");
  await expect(page.getByText("alpha 只读版不显示")).toHaveCount(0);
  await rows.nth(1).dblclick();
  const dialog = page.locator("[data-role=log-details]");
  await expect(dialog.locator("h2")).toHaveText("日志详情");
  await expect(dialog.locator("[data-role=log-details-text]")).toContainText("类别：通信异常（communication）");
  await expect(dialog.locator("[data-role=log-details-text]")).toContainText("设备：温室外");
  await dialog.locator("[data-role=log-close]").click();
  await expect(dialog).toHaveCount(0);
});

test("采集记录导出：预设与自定义范围的预计记录数，否不写文件，是按设备/格式/日期写出（EXP-011、EXP-053、D-210）", async ({
  page,
}) => {
  await openSettings(page);
  const total = await dayCount(page.request);
  expect(total).toBeGreaterThan(0);
  // the database holds 2026-10-01 only: the last hour (by the service clock) holds nothing (EXP-049)
  await expect(page.locator("[data-role=count]")).toHaveText("预计 0 条记录，将导出为 0 个文件");
  await expect(page.locator("input[name=export-start]")).toBeDisabled();
  await expect(page.locator("[data-role=export-button]")).toBeDisabled();

  await customDay(page);
  await expect(page.locator("[data-role=count]")).toHaveText(`预计 ${total} 条记录，将导出为 ${total} 个文件`);
  await page.getByLabel("Excel (.xlsx)").check();
  await expect(page.locator("[data-role=count]")).toHaveText(`预计 ${total} 条记录，将导出为 ${2 * total} 个文件`);

  await page.locator("[data-role=export-button]").click();
  const dialog = page.getByRole("dialog");
  await expect(dialog).toContainText("导出设备：温室外");
  await expect(dialog).toContainText(`时间范围：2026-10-01 00:00:00 至 2026-10-01 23:59:59`);
  await dialog.getByRole("button", { name: "否" }).click();
  await expect(dialog).toHaveCount(0);
  expect(exported("CSV")).toEqual([]);

  await page.locator("[data-role=export-button]").click();
  await page.getByRole("dialog").getByRole("button", { name: "是" }).click();
  await expect(page.locator("[data-role=export-done]")).toContainText(`已导出 ${2 * total} 个文件到`, { timeout: 30_000 });
  const csv = exported("CSV");
  expect(csv).toHaveLength(total);
  expect(exported("Excel")).toHaveLength(total);
  expect(csv[0]).toMatch(/^PAR_20261001_\d{6}_#\d+\.csv$/);
});

test("采集记录导出：统计失败时保留上次结果并可重试（R-1-5）", async ({ page }) => {
  await openSettings(page);
  await customDay(page);
  const shown = page.locator("[data-role=count]");
  // wait for the custom day's count, not the preset's "预计 0 条" still on screen before it arrives
  await expect(shown).toHaveText(/^预计 [1-9]\d* 条记录，将导出为/);
  const before = await shown.textContent();

  await page.route(COUNT, (route) => route.abort());
  await page.getByLabel("Excel (.xlsx)").check();
  const notice = page.getByRole("alert").filter({ hasText: "预计记录数为上次统计的结果" });
  await expect(notice).toBeVisible();
  await expect(shown).toHaveText(before ?? "");

  await page.unroute(COUNT);
  await notice.getByRole("button", { name: "重试" }).click();
  await expect(notice).toHaveCount(0);
  await expect(shown).not.toHaveText(before ?? "");
});

test("导出诊断包与维护记录：只读，诊断包写到 alpha 输出目录（D-226）", async ({ page }) => {
  await openSettings(page);
  const log = page.locator("[data-role=maintenance-log]");
  await expect(log.locator("[data-role=log-empty]")).toBeVisible({ timeout: 20_000 }); // devices, no maintenance yet
  await page.locator("[data-role=diagnostics-export]").click();
  const done = page.locator("[data-role=diagnostics-done]");
  await expect(done).toContainText("已保存诊断包：", { timeout: 20_000 });
  const folder = join(process.env.PAR_E2E_DATA_DIR ?? "", "exports", "diagnostics");
  const zips = readdirSync(folder).filter((name) => name.endsWith(".zip"));
  expect(zips.length).toBeGreaterThan(0);
  await expect(done).toContainText(zips[zips.length - 1] ?? "");
  expect(readdirSync(folder).some((name) => name.endsWith(".partial"))).toBe(false);
});

async function screenshot(browser: Browser, scale: number, folder: string): Promise<void> {
  const context = await browser.newContext({
    viewport: { width: 1680, height: 900 },
    deviceScaleFactor: scale,
  });
  const page = await context.newPage();
  await openSettings(page);
  const total = await dayCount(page.request);
  await customDay(page);
  await page.getByLabel("Excel (.xlsx)").check();
  await expect(page.locator("[data-role=count]")).toHaveText(`预计 ${total} 条记录，将导出为 ${2 * total} 个文件`);
  await expect(page.locator("[data-role=status]")).toContainText("最近采集");
  // The output folder is the e2e scratch folder of this machine; committed images must not show a developer's path
  // (R-4-7, review of PR #52), so the line shows a neutral placeholder and the test proves no path is left on screen.
  const directory = page.locator("[data-role=export] .directory");
  await expect(directory).toContainText(SCRATCH);
  await directory.evaluate((element, text) => {
    element.textContent = text;
    element.setAttribute("title", text);
  }, NEUTRAL_DIRECTORY);
  await expect(page.locator("body")).not.toContainText(SCRATCH);
  await page.screenshot({ path: join(folder, `export-${Math.round(scale * 100)}.png`) });
  await context.close();
}

test("截图：1680×900，100% 与 150%（只在设置 PAR_SCREENSHOT_DIR 时运行）", async ({ browser }) => {
  const folder = process.env.PAR_SCREENSHOT_DIR;
  test.skip(!folder, "PAR_SCREENSHOT_DIR is not set");
  for (const scale of [1, 1.5]) await screenshot(browser, scale, folder ?? "");
});
