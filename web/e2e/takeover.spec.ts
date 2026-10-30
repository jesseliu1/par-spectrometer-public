/**
 * Tier 1 "接管采集" end to end (16_ 7.7; D-214): Chromium against the real alpha service on the byte-level fake bus
 * (tests/support/fake_bus_service.py patches serial.Serial before the service starts; product code has no fake
 * mode), with its own fresh data directory, so the shared tier-0 service of setup.ts is never switched.
 *
 * One round: 档位 0 → the two confirmation layers → 档位 1 · 未接管 → 开始采集 → register two devices on the
 * settings page and save (V1.0.3's DeviceHub.apply on the service) → the live overview shows a record the event
 * stream announced → 停止采集 (asks first) → 切回档位 0 (asks first). The status bar's tier block is checked at every
 * step. With PAR_SCREENSHOT_DIR set it also writes live-overview-100.png and live-settings-100.png (1680×900, local
 * paths masked; R-4-7).
 */
import { spawn, type ChildProcess } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { expect, test, type Page } from "@playwright/test";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const SCRATCH = "par-e2e-takeover-";
const START_MS = 30_000;
const RECORD_MS = 45_000;
/** Stopping waits for the transaction in progress (at most one acquisition budget, 40 s). */
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
  const venv = join(
    root,
    ".venv",
    ...(process.platform === "win32"
      ? ["Scripts", "python.exe"]
      : ["bin", "python"]),
  );
  return existsSync(venv) ? venv : "python";
}

async function startService(): Promise<Service> {
  const scratch = mkdtempSync(join(tmpdir(), SCRATCH));
  const dataDir = join(scratch, "alpha");
  const child = spawn(
    python(),
    [
      join(root, "tests", "support", "fake_bus_service.py"),
      ...[
        "--port",
        "0",
        "--data-dir",
        dataDir,
        "--web-dir",
        join(root, "web", "dist"),
      ],
    ],
    {
      cwd: root,
      stdio: ["ignore", "ignore", "pipe"],
      // the fake probes answer at the blank form's default, 57600 bps, no parity (the delivered bus)
      env: { ...process.env, QT_QPA_PLATFORM: "offscreen", PAR_TEST_DELIVERED_BUS: "1" },
    },
  );
  let stderr = "";
  child.stderr?.on("data", (chunk: Buffer) => (stderr += chunk.toString()));
  const deadline = Date.now() + START_MS;
  while (Date.now() < deadline) {
    if (child.exitCode !== null)
      throw new Error(
        `fake-bus service exited with ${child.exitCode}: ${stderr}`,
      );
    try {
      const info = JSON.parse(
        readFileSync(join(dataDir, "service.json"), "utf-8"),
      ) as { base_url: string; token: string };
      if ((await fetch(`${info.base_url}/api/v0/health`)).ok)
        return { child, scratch, base: info.base_url, token: info.token };
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

async function open(page: Page, view: string): Promise<void> {
  const running = service as Service;
  await page.goto(
    `${running.base}/?view=${view}#token=${encodeURIComponent(running.token)}`,
  );
}

async function goTo(page: Page, name: string): Promise<void> {
  // the tab's own label (a tab may carry a tag; none does at present, #82)
  const tab = page
    .getByRole("navigation", { name: "主导航" })
    .locator("button", {
      has: page.locator(".label", { hasText: new RegExp(`^${name}$`) }),
    });
  await tab.click();
  await expect(tab).toHaveAttribute("aria-current", "page");
}

async function screenshot(page: Page, name: string): Promise<void> {
  const folder = process.env.PAR_SCREENSHOT_DIR;
  if (!folder) return;
  await page.setViewportSize({ width: 1680, height: 900 });
  const paths = page.locator(
    "[data-role=config-path], [data-role=settings-path], [data-role=export] .directory",
  );
  let visible = await page.locator("body").innerText();
  for (const text of await paths.allInnerTexts())
    visible = visible.replace(text, "");
  expect(visible).not.toContain(SCRATCH); // only the masked path lines may name the scratch folder
  await page.screenshot({
    path: join(folder, `${name}-100.png`),
    mask: [paths],
  });
  await page.setViewportSize({ width: 1440, height: 1000 });
}

test("档位 1：开启（两层确认）→ 开始采集 → 登记并保存 → 收到记录 → 停止 → 设置页无只读切换（issue 119）", async ({
  page,
}) => {
  test.setTimeout(240_000);
  await open(page, "settings");
  await expect(tierText(page)).toHaveText("只读模式（不连接设备）");

  // 0 → 1: the service's notice, then the checkbox; "开启档位 1" stays disabled until it is checked
  await page.locator("[data-role=tier-up]").click();
  const dialog = page.locator("[data-role=tier-dialog]");
  await expect(dialog.locator("[data-role=tier-notice]")).toContainText(
    "采集期间其他软件不能使用该串口",
  );
  await dialog.locator("[data-role=tier-next]").click();
  await expect(dialog.locator("[data-role=tier-accept]")).toBeDisabled();
  await dialog.getByRole("checkbox").check();
  await dialog.locator("[data-role=tier-accept]").click();
  await expect(dialog).toHaveCount(0);
  await expect(tierText(page)).toHaveText("采集模式 · 未在采集（可点“开始采集”）");
  await expect(page.locator("[data-role=config-path]")).toContainText(
    "app_config.json",
  );

  // start the takeover from the overview: the real takeover state and the bus state
  await goTo(page, "实时概览");
  await expect(page.locator("[data-role=snapshot]")).toHaveCount(0);
  await expect(
    page.locator("[data-view=overview] [data-role=snapshot-tag]"),
  ).toHaveCount(0); // tier 1: not a snapshot
  await page.locator("[data-role=start]").click();
  // nothing registered yet: running, but the mode says so instead of 正在采集 (负责人 2026-10-27)
  const waiting = "采集模式 · 等待登记设备（请到“设置与导出”登记并保存）";
  await expect(tierText(page)).toHaveText(waiting, { timeout: START_MS });
  await expect(page.locator("[data-role=takeover-text]")).toHaveText(waiting);
  await expect(page.locator("[data-role=stop]")).toBeEnabled();

  // first use: register two devices and save; V1.0.3's DeviceHub.apply decides on the service
  await goTo(page, "设置与导出");
  await page.locator("input[name=bus-serial-port]").fill("COM7");
  await page.locator("input[name=device-name-0]").fill("North");
  await page.locator("input[name=device-enabled-0]").check();
  await page.locator("input[name=device-name-1]").fill("South");
  await page.locator("input[name=device-enabled-1]").check();
  await page.locator("[data-role=config-save]").click();
  await expect(page.locator("[data-role=config-saved]")).toHaveText(
    "配置已保存，等待当前事务结束后应用。",
  );
  await expect(
    page.locator("[data-role=devices] tbody tr").first(),
  ).toContainText("North.sqlite3");
  await expect(tierText(page)).toHaveText("采集模式 · 正在采集");

  // the live overview shows a saved record of p1, announced by the event stream
  await goTo(page, "实时概览");
  await expect(page.locator("[data-role=live-banner]")).toHaveText(
    "实时数据",
  );
  await expect(page.locator("[data-role=bus-state]")).toHaveText(
    "总线已连接",
    { timeout: RECORD_MS },
  );
  // issue 136: the bus line names its record, and the same record is in the alpha's logs/events.jsonl
  const busTitle = (await page.locator("[data-role=bus-state]").getAttribute("title")) ?? "";
  const recorded = /记录号 (\S+)，出现于 /.exec(busTitle);
  expect(recorded, busTitle).not.toBeNull();
  const eventsFile = join(service!.scratch, "alpha", "logs", "events.jsonl");
  const recordOf = (id: string) =>
    (existsSync(eventsFile) ? readFileSync(eventsFile, "utf-8").trim().split("\n") : [])
      .filter((line) => line)
      .map((line) => JSON.parse(line) as { event_id: string; kind: string; message: string })
      .find((event) => event.event_id === id); // written by the service's writer thread, a moment later
  await expect.poll(() => recordOf(recorded?.[1] ?? "")).toMatchObject({ kind: "bus", message: "总线已连接" });
  await expect(
    page.locator("[data-role=live-devices] [data-key=p1]"),
  ).toHaveAttribute("aria-pressed", "true");
  await expect(page.locator("[data-role=status]")).toContainText("显示 #", {
    timeout: RECORD_MS,
  });
  await expect(page.locator("[data-role=kpis] .value").first()).not.toHaveText(
    "—",
  );
  await screenshot(page, "live-overview");
  await goTo(page, "设置与导出");
  await screenshot(page, "live-settings");
  await goTo(page, "实时概览");

  // stop asks first; "否" changes nothing
  await page.locator("[data-role=stop]").click();
  await page.locator("[data-role=confirm-no]").click();
  await expect(tierText(page)).toHaveText(
    "采集模式 · 正在采集",
  );
  await page.locator("[data-role=stop]").click();
  await expect(page.getByRole("dialog")).toContainText(
    "停止采集后，本软件释放串口",
  );
  await page.locator("[data-role=confirm-yes]").click();
  await expect(tierText(page)).toHaveText("采集模式 · 未在采集（可点“开始采集”）", {
    timeout: STOP_MS,
  });
  await expect(page.locator("[data-role=bus-state]")).toHaveText(
    "总线：未在采集：未连接设备",
  );
  await expect(page.locator("[data-role=live-banner]")).toHaveText(
    "未在采集：显示设备库中的最后数据",
  );

  // issue 119: the page offers no way back to read-only; the settings panel only switches maintenance
  await goTo(page, "设置与导出");
  await expect(page.locator("[data-role=tier-down]")).toHaveCount(0);
  await expect(page.locator("[data-role=tier-up-2]")).toHaveText("开启维护模式…");
  await expect(page.getByText("切回只读模式")).toHaveCount(0);
});
