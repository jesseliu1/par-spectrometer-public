/**
 * Tier 2 "设备维护" end to end (17_ 10.5): Chromium against the real alpha service on the byte-level fake bus
 * (tests/support/fake_bus_service.py patches serial.Serial before the service starts; product code has no fake mode),
 * with its own fresh data directory.
 *
 * One round: 档位 0 → 1 → 2 (two confirmation layers each) → 开始采集 → register two devices → 设备维护: the
 * diagnostics tab reads by itself → 光谱校准 reads by itself → change a value → 写入硬件并回读 (the service's confirmation
 * text, 是) → 通信参数维护: 停止全部采集并进入通信维护 (是) → 读取目标设备 → 确认并写入 a new address (是) → automatic
 * verification → the operator updates the registration on the settings page → 退出通信维护并恢复采集 (是) → the device
 * answers on its new address → 停止采集. With PAR_SCREENSHOT_DIR set it writes maint-*.png (1680×900, local paths
 * masked; R-4-7).
 */
import { spawn, type ChildProcess } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const SCRATCH = "par-e2e-maintenance-";
const START_MS = 30_000;
const DEVICE_MS = 60_000;
const STOP_MS = 60_000;

interface Service {
  child: ChildProcess;
  scratch: string;
  base: string;
  token: string;
}

let service: Service | null = null;

function python(): string {
  if (process.env.PAR_E2E_PYTHON) return process.env.PAR_E2E_PYTHON;
  const venv = join(root, ".venv", ...(process.platform === "win32" ? ["Scripts", "python.exe"] : ["bin", "python"]));
  return existsSync(venv) ? venv : "python";
}

async function startService(): Promise<Service> {
  const scratch = mkdtempSync(join(tmpdir(), SCRATCH));
  const dataDir = join(scratch, "alpha");
  const child = spawn(
    python(),
    [
      join(root, "tests", "support", "fake_bus_service.py"),
      ...["--port", "0", "--data-dir", dataDir, "--web-dir", join(root, "web", "dist")],
    ],
    { cwd: root, stdio: ["ignore", "ignore", "pipe"], env: { ...process.env, QT_QPA_PLATFORM: "offscreen", PAR_TEST_DELIVERED_BUS: "1" } },
  );
  let stderr = "";
  child.stderr?.on("data", (chunk: Buffer) => (stderr += chunk.toString()));
  const deadline = Date.now() + START_MS;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`fake-bus service exited with ${child.exitCode}: ${stderr}`);
    try {
      const info = JSON.parse(readFileSync(join(dataDir, "service.json"), "utf-8")) as { base_url: string; token: string };
      if ((await fetch(`${info.base_url}/api/v0/health`)).ok) return { child, scratch, base: info.base_url, token: info.token };
    } catch {
      // not listening yet
    }
    await new Promise((wake) => setTimeout(wake, 100));
  }
  child.kill("SIGKILL");
  throw new Error(`fake-bus service not ready: ${stderr}`);
}

test.beforeAll(async () => {
  service = await startService();
});

test.afterAll(async () => {
  if (service === null) return;
  const { child, scratch } = service;
  const gone = new Promise<void>((done) => child.once("exit", () => done()));
  child.kill("SIGTERM");
  const timer = setTimeout(() => child.kill("SIGKILL"), STOP_MS);
  await gone;
  clearTimeout(timer);
  rmSync(scratch, { recursive: true, force: true });
});

const tierText = (page: Page) => page.locator("[data-role=tier-text]");

async function goTo(page: Page, name: string): Promise<void> {
  const tab = page
    .getByRole("navigation", { name: "主导航" })
    .locator("button", { has: page.locator(".label", { hasText: new RegExp(`^${name}$`) }) });
  await tab.click();
  await expect(tab).toHaveAttribute("aria-current", "page");
}

async function raiseTier(page: Page, button: string, tier: number): Promise<void> {
  await page.locator(`[data-role=${button}]`).click();
  const dialog = page.locator("[data-role=tier-dialog]");
  await expect(dialog).toContainText(tier === 2 ? "开启维护模式" : "开启采集模式");
  await dialog.locator("[data-role=tier-next]").click();
  await dialog.getByRole("checkbox").check();
  await dialog.locator("[data-role=tier-accept]").click();
  await expect(dialog).toHaveCount(0);
}

/** 是 in the service's confirmation dialog, after checking its title. */
async function yes(page: Page, title: string): Promise<void> {
  const dialog = page.getByRole("dialog", { name: title });
  await expect(dialog).toBeVisible();
  await dialog.locator("[data-role=confirm-yes]").click();
  await expect(dialog).toHaveCount(0);
}

async function screenshot(page: Page, name: string): Promise<void> {
  const folder = process.env.PAR_SCREENSHOT_DIR;
  if (!folder) return;
  await page.setViewportSize({ width: 1680, height: 900 });
  const paths = page.locator("[data-role=config-path], [data-role=settings-path], [data-role=maintenance-result], [data-role=diagnostics-done], [data-role=export] .directory");
  let visible = await page.locator("body").innerText();
  for (const text of await paths.allInnerTexts()) visible = visible.replace(text, "");
  expect(visible).not.toContain(SCRATCH); // only masked lines may name the scratch folder
  await page.screenshot({ path: join(folder, `maint-${name}.png`), mask: [paths] });
  await page.setViewportSize({ width: 1440, height: 1000 });
}

async function registerDevices(page: Page, northAddress: number | null = null): Promise<void> {
  await goTo(page, "设置与导出");
  if (northAddress === null) {
    await page.locator("input[name=bus-serial-port]").fill("COM7");
    await page.locator("input[name=device-name-0]").fill("North");
    await page.locator("input[name=device-enabled-0]").check();
    await page.locator("input[name=device-name-1]").fill("South");
    await page.locator("input[name=device-enabled-1]").check();
  } else {
    // the editor commits a number on change; a re-render before that (status events arrive while typing) puts
    // the draft's value back into the box, so type, commit and check that the draft took it (retry if not)
    const slave = page.locator("input[name=device-slave-0]");
    await expect(async () => {
      await slave.fill(String(northAddress));
      await slave.press("Tab");
      await expect(slave).toHaveValue(String(northAddress), { timeout: 1_000 });
    }).toPass({ timeout: 10_000 });
  }
  const saved = page.waitForResponse(
    (response) => response.url().endsWith("/api/v0/acquisition-config") && response.request().method() === "PUT",
  );
  await page.locator("[data-role=config-save]").click();
  const response = await saved;
  expect(response.status(), await response.text()).toBe(200);
  if (northAddress !== null) expect(((await response.json()) as { devices: { slave_id: number }[] }).devices[0]?.slave_id).toBe(northAddress);
  await expect(page.locator("[data-role=config-saved]")).toHaveText("配置已保存，等待当前事务结束后应用。");
}

test("档位 2：开启 → 进入维护 → 读校准 → 改值 → 写入 → 改地址并核对 → 退出维护并恢复采集", async ({ page }) => {
  test.setTimeout(420_000);
  const running = service as Service;
  await page.goto(`${running.base}/?view=settings#token=${encodeURIComponent(running.token)}`);
  await expect(tierText(page)).toHaveText("只读模式（不连接设备）");
  await raiseTier(page, "tier-up", 1);
  await raiseTier(page, "tier-up-2", 2);
  await expect(tierText(page)).toHaveText("维护模式 · 未在采集（可点“开始采集”）");

  await goTo(page, "实时概览");
  await page.locator("[data-role=start]").click();
  await expect(tierText(page)).toHaveText("维护模式 · 等待登记设备（请到“设置与导出”登记并保存）", {
    timeout: START_MS,
  });
  await registerDevices(page);
  await expect(tierText(page)).toHaveText("维护模式 · 正在采集");
  await goTo(page, "实时概览");
  await expect(page.locator("[data-role=status]")).toContainText("显示 #", { timeout: DEVICE_MS });

  // diagnostics: the tab reads once by itself (MAINT-025)
  await goTo(page, "设备维护");
  await expect(page.locator("[data-role=diagnostics-identity]")).toContainText("PAR-FAKE", { timeout: DEVICE_MS });
  await screenshot(page, "diagnostics");

  // calibration: reads by itself, a value changed, written after the service's confirmation, read back
  await page.locator(".tabs .tab", { hasText: "光谱校准" }).click();
  await expect(page.locator("[data-role=calibration-write]")).toBeEnabled({ timeout: DEVICE_MS });
  const y1 = page.locator("input[name=calibration-y1]");
  await y1.fill("-1.5");
  await y1.dispatchEvent("change");
  await expect(page.locator("[data-role=calibration-value-state]")).toHaveText("待写入修改");
  await page.locator("[data-role=calibration-write]").click();
  await expect(page.getByRole("dialog", { name: "确认校准写入" })).toContainText("→ -0.015");
  await screenshot(page, "calibration-confirm");
  await yes(page, "确认校准写入");
  await expect(page.locator("[data-role=calibration-value-state]")).toHaveCount(0, { timeout: DEVICE_MS });
  await expect(page.locator("[data-role=calibration-info]")).toContainText("校准状态码：3");
  await screenshot(page, "calibration");

  // communication maintenance: enter, read, write a new address; the service verifies by itself
  await page.locator(".tabs .tab", { hasText: "通信参数维护" }).click();
  await page.locator("[data-role=maintenance-enter]").click();
  await yes(page, "停止全部采集并进入维护");
  await expect(tierText(page)).toHaveText("维护模式 · 通信维护中，采集已暂停", { timeout: DEVICE_MS });
  await page.locator("input[name=maintenance-port]").fill("COM7");
  await page.locator("input[name=maintenance-isolated]").check();
  await page.locator("[data-role=comm-read]").click();
  await expect(page.locator("[data-role=communication-state]")).toHaveText("目标设备已读取，请核对身份与准备写入值。", {
    timeout: DEVICE_MS,
  });
  const address = page.locator("input[name=maintenance-new-slave]");
  await address.fill("9");
  await address.dispatchEvent("change");
  await page.locator("[data-role=comm-write]").click();
  await expect(page.getByRole("dialog", { name: "确认硬件写入" })).toContainText('"slave_id": 9');
  await yes(page, "确认硬件写入");
  await expect(page.locator("[data-role=communication-state]")).toContainText("设备身份和新参数核对通过", {
    timeout: DEVICE_MS,
  });
  await expect(page.locator("[data-role=resume-reason]")).toContainText("请先在常规设置中手动更新该设备 ID");
  await screenshot(page, "communication-verified");

  // the registration is updated by hand (MAINT-003), then acquisition resumes
  await registerDevices(page, 9);
  await goTo(page, "设备维护");
  await expect(page.locator("[data-role=maintenance-leave]")).toBeEnabled({ timeout: DEVICE_MS });
  await page.locator("[data-role=maintenance-leave]").click();
  await yes(page, "确认恢复采集");
  await expect(tierText(page)).toHaveText("维护模式 · 正在采集", { timeout: DEVICE_MS });
  await expect(page.locator("[data-role=maintenance-state]")).not.toContainText("维护", { timeout: DEVICE_MS });
  await screenshot(page, "resumed");

  await goTo(page, "实时概览");
  await page.locator("[data-role=stop]").click();
  await page.locator("[data-role=confirm-yes]").click();
  await expect(tierText(page)).toHaveText("维护模式 · 未在采集（可点“开始采集”）", { timeout: STOP_MS });

  // 维护记录 (D-226): the writes above, read back from North's database; then a diagnostics bundle
  await goTo(page, "设置与导出");
  const log = page.locator("[data-role=maintenance-log]");
  await log.locator("select[name=log-device]").selectOption({ label: "North" });
  const rows = log.locator("[data-role=log-table] tbody tr");
  await expect(rows).toHaveCount(3, { timeout: DEVICE_MS });
  await expect(rows.nth(0)).toContainText("通信参数核对");
  await expect(rows.nth(1)).toContainText("通信参数写入");
  await expect(rows.nth(1)).toContainText("地址 9");
  await expect(rows.nth(2)).toContainText("校准写入");
  await expect(log.locator("[data-role=log-result]")).toHaveText(["成功", "成功", "成功"]);
  await page.locator("[data-role=diagnostics-export]").click();
  await expect(page.locator("[data-role=diagnostics-done]")).toContainText("PAR_diagnostics_", { timeout: DEVICE_MS });
  await page.locator("[data-role=maintenance-log]").scrollIntoViewIfNeeded();
  await screenshot(page, "support");
});
