/**
 * The top bar's run status (issue #73; UI-253, UI-252, UI-256): V1.0.3's "总线：… ｜ 采集…" block and its red
 * failure lines, on every page. The texts and their levels come from the service (GET /acquisition/status
 * `run_status`); before a takeover runs the block shows the tier, and at tier 0 "未连接设备 / 只读" (D-227).
 */
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import type { ApiClient } from "../src/api/client";
import type { AcquisitionStatus, RunStatus, Takeover, TierLevel, TierState } from "../src/api/types";
import App from "../src/App.vue";
import RunStatusBar from "../src/components/RunStatus.vue";
import { LOADING_TEXT, noticeText, runStatusView, TIER0_TEXT, withNotice } from "../src/lib/runStatus";
import { createCalcStore } from "../src/pages/calcStore";
import { createDliStore } from "../src/pages/dliStore";
import { createHistoryStore } from "../src/pages/historyStore";
import { createOverviewStore } from "../src/pages/overviewStore";
import { createSettingsStore } from "../src/pages/settingsStore";
import { createTakeoverStore } from "../src/pages/takeoverStore";
import { AS_OF, detail, devices, health, overview, page, snapshots } from "./fixtures";

vi.mock("echarts/core", () => ({
  use: () => undefined,
  init: () => ({ setOption: () => undefined, resize: () => undefined, dispose: () => undefined }),
}));

const PORT_FAILED = "总线连接失败：could not open port 'COM6': FileNotFoundError";
const FAILURE_LINE = `2026-10-26 09:00:00.123  North（地址 1）  连续第 17 次尝试失败：${PORT_FAILED}（未启用失败停止，将继续按周期重试）`;

function failing(): RunStatus {
  return {
    bus: { text: "总线：异常", level: "error", detail: PORT_FAILED },
    acquisition: { text: "采集运行中：等待设备响应", level: "warn" },
    failures: [FAILURE_LINE],
  };
}

function tierState(tier: number, takeover: Takeover, text: string, level: TierLevel): TierState {
  return {
    tier,
    takeover,
    lock_held: takeover === "running",
    text,
    level,
    settings_path: "/alpha/config/app_config_v2.json",
    settings_problem: null,
    stop_text: "停止确认",
    down_text: "切回档位 0 确认",
    down_to_1_text: "切回档位 1 确认",
    maintenance: false,
    fault: null,
  };
}

const TIER0 = tierState(0, "released", "只读模式（不连接设备）", "muted");
const RELEASED = tierState(1, "released", "采集模式 · 未在采集（可点“开始采集”）", "info");
const RUNNING = tierState(1, "running", "采集模式 · 正在采集", "warn");

function status(run: RunStatus, takeover: Takeover = "running"): AcquisitionStatus {
  return {
    as_of: AS_OF,
    takeover,
    lock_held: takeover === "running",
    error: null,
    bus: { level: "error", message: PORT_FAILED },
    halt: null,
    maintenance: false,
    poll_cycle_seconds: 40,
    config_apply_error: null,
    devices: [],
    run_status: run,
  };
}

describe("runStatusView", () => {
  it("tier 0 reads 未连接设备 / 只读 and never 采集运行中 (issue #73 criterion 3)", () => {
    const view = runStatusView(TIER0, null);
    expect(view).toEqual({
      bus: null,
      acquisition: { text: TIER0_TEXT, level: "muted" },
      failures: [],
      failureNotices: [],
    });
    // issue 119: before the tier is read the product is not called read-only (it acquires by default)
    expect(runStatusView(null, null).acquisition.text).toBe(LOADING_TEXT);
    expect(TIER0_TEXT).toBe("未连接设备 / 只读");
    // a status left over from an earlier takeover is not shown once released at tier 0
    expect(runStatusView(TIER0, status(failing(), "released")).acquisition.text).toBe(TIER0_TEXT);
  });

  it("tier 1 without a running takeover shows the service's tier text", () => {
    expect(runStatusView(RELEASED, null)).toEqual({
      bus: null,
      acquisition: { text: RELEASED.text, level: "info" },
      failures: [],
      failureNotices: [],
    });
    expect(runStatusView(RUNNING, null).acquisition.text).toBe(RUNNING.text); // status not read yet
  });

  it("a running takeover shows the service's run status (issue #73 criteria 1 and 2)", () => {
    expect(runStatusView(RUNNING, status(failing()))).toEqual({ ...failing(), failureNotices: [null] });
  });

  it("carries the record of each line so it can be found in the diagnostics bundle (issue 136)", () => {
    const notice = { event_id: "3f9a1c2b-000017", occurred_at: "2026-10-26T09:00:00.123" };
    const run = { ...failing(), bus: { ...failing().bus, notice }, failure_notices: [notice] };
    const view = runStatusView(RUNNING, status(run));
    expect(view.failureNotices).toEqual([notice]);
    expect(noticeText(notice)).toBe("记录号 3f9a1c2b-000017，出现于 2026-10-26 09:00:00.123");
    expect(noticeText(null)).toBe("");
    expect(withNotice("总线已连接", null)).toBe("总线已连接");
    const wrapper = mount(RunStatusBar, { props: { view } });
    expect(wrapper.get("[data-role=run-bus]").attributes("title")).toBe(`${PORT_FAILED}\n${noticeText(notice)}`);
  });

  it("a takeover still running while the tier reads 0 keeps the run status (D-215)", () => {
    const held = tierState(0, "running", "只读模式（不连接设备）", "muted");
    expect(runStatusView(held, status(failing())).acquisition.text).toBe("采集运行中：等待设备响应");
  });
});

describe("RunStatus component", () => {
  it("shows 总线 and 采集 with level classes and the bus message on hover", () => {
    const wrapper = mount(RunStatusBar, { props: { view: { ...failing(), failureNotices: [] } } });
    const bus = wrapper.get("[data-role=run-bus]");
    expect(bus.text()).toBe("总线：异常");
    expect(bus.classes()).toContain("error");
    expect(bus.attributes("title")).toBe(PORT_FAILED);
    const acquisition = wrapper.get("[data-role=run-acquisition]");
    expect(acquisition.text()).toBe("采集运行中：等待设备响应");
    expect(acquisition.classes()).toContain("warn");
  });

  it("has no bus part when there is no running takeover", () => {
    const wrapper = mount(RunStatusBar, { props: { view: runStatusView(TIER0, null) } });
    expect(wrapper.find("[data-role=run-bus]").exists()).toBe(false);
    expect(wrapper.get("[data-role=run-acquisition]").text()).toBe("未连接设备 / 只读");
  });
});

function appApi(tier: TierState, run: RunStatus | null) {
  return {
    tier: vi.fn(async () => tier),
    acquisitionStatus: vi.fn(async () => status(run ?? failing(), tier.takeover)),
    openEvents: vi.fn(),
    health: vi.fn(async () => health()),
    snapshots: vi.fn(async () => snapshots()),
    devices: vi.fn(async () => devices(["p1"])),
    acquisitions: vi.fn(async () => page([])),
    acquisition: vi.fn(async (key: string, id: number) => detail(id, key)),
    overview: vi.fn(async (key: string) => overview(key)),
    liveOverview: vi.fn(async () => {
      throw new Error("not used");
    }),
  };
}

async function mountApp(tier: TierState, run: RunStatus | null) {
  const client = appApi(tier, run) as unknown as ApiClient;
  const wrapper = mount(App, {
    props: {
      store: createHistoryStore(client),
      dli: createDliStore(client),
      calc: createCalcStore(client),
      settings: createSettingsStore(client),
      overview: createOverviewStore(client),
      takeover: createTakeoverStore(client, { connect: false }),
      initialView: "overview",
    },
    global: { stubs: { SpectrumChart: true, OverviewChart: true, DliChart: true, CalibrationChart: true } },
  });
  await flushPromises();
  return wrapper;
}

const VIEWS = ["overview", "history", "calc", "dli", "settings"];

describe("App top status area", () => {
  it("is in the top bar and stays visible on every page (issue #73 criterion 4)", async () => {
    const wrapper = await mountApp(RUNNING, failing());
    for (const view of VIEWS) {
      await wrapper.get(`[data-view=${view}]`).trigger("click");
      await flushPromises();
      const bar = wrapper.get("header [data-role=run-status]");
      expect(bar.get("[data-role=run-bus]").text()).toBe("总线：异常");
      expect(bar.get("[data-role=run-acquisition]").text()).toBe("采集运行中：等待设备响应");
      const failures = wrapper.get("[data-role=run-failures]");
      expect(failures.text()).toBe(FAILURE_LINE); // UI-252: its own red row below the bar
      expect(failures.element.closest("header")).toBeNull();
    }
    wrapper.unmount();
  });

  it("at tier 0 reads 未连接设备 / 只读 on every page and no 采集运行中", async () => {
    const wrapper = await mountApp(TIER0, null);
    for (const view of VIEWS) {
      await wrapper.get(`[data-view=${view}]`).trigger("click");
      await flushPromises();
      expect(wrapper.get("header [data-role=run-acquisition]").text()).toBe("未连接设备 / 只读");
      expect(wrapper.get("header").text()).not.toContain("采集运行中");
      expect(wrapper.find("[data-role=run-failures]").exists()).toBe(false); // UI-142: hidden without failures
    }
    wrapper.unmount();
  });
});
