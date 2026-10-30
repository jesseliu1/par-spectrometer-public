import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "../src/api/client";
import type { ExportCountQuery, ExportKind } from "../src/api/types";
import App from "../src/App.vue";
import SettingsPage from "../src/pages/SettingsPage.vue";
import { createCalcStore } from "../src/pages/calcStore";
import { createDliStore } from "../src/pages/dliStore";
import { createHistoryStore } from "../src/pages/historyStore";
import { createOverviewStore } from "../src/pages/overviewStore";
import { chosenFormats, createSettingsStore, exportDevices, normaliseTime } from "../src/pages/settingsStore";
import { PAGES } from "../src/lib/view";
import {
  deviceLog,
  deviceSummary,
  devices,
  exportCount,
  exported,
  health,
  jsonResponse,
  NO_CONFIG,
  page,
  settingsView,
  snapshots,
} from "./fixtures";

const unavailable = () =>
  new ApiError(503, { code: "database_unavailable", message: "数据库不可访问：/alpha/p1.sqlite", retryable: true, detail: null });

function settingsApi(configured: string[] = ["p1", "p2"]) {
  return {
    settings: vi.fn(async () => settingsView(configured)),
    deviceSummary: vi.fn(async (key: string) => deviceSummary(key)),
    deviceLogs: vi.fn(async (key: string) => deviceLog(key)),
    exportCount: vi.fn(async (key: string, query: ExportCountQuery) => exportCount({ key, ...query })),
    exportAcquisitions: vi.fn(async () => exported(3)),
  };
}

function store(api = settingsApi()) {
  return { api, settings: createSettingsStore(api as unknown as ApiClient) };
}

describe("settings store: export device, range and count (EXP-041..051)", () => {
  it("defaults the export device to the viewed device on the first visit, then keeps it (EXP-042)", async () => {
    const { api, settings } = store();
    await settings.show("p2");
    expect(settings.state.exportKey).toBe("p2");
    expect(api.exportCount).toHaveBeenLastCalledWith("p2", { range: "1h", formats: ["csv"] });
    expect(settings.state.count.data?.text).toBe("预计 3 条记录，将导出为 3 个文件");
    await settings.show("p1");
    expect(settings.state.exportKey).toBe("p2"); // the viewed device changed, the export device did not (EXP-041)
    expect(settings.state.summaryKey).toBe("p1"); // the status area follows the viewed device (UI-080)
    expect(api.deviceSummary).toHaveBeenLastCalledWith("p1");
  });

  it("falls back to the first imported position when the viewed one has no snapshot", async () => {
    const { settings } = store(settingsApi(["p3", "p4"]));
    await settings.show("p1");
    expect(settings.state.exportKey).toBe("p3");
    expect(exportDevices(settings.state).map((item) => item.key)).toEqual(["p3", "p4"]); // EXP-047
  });

  it("without any snapshot there is no export device and no count (EXP-049)", async () => {
    const api = settingsApi([]);
    const { settings } = store(api);
    await settings.show(null);
    expect(settings.state.exportKey).toBeNull();
    expect(api.exportCount).not.toHaveBeenCalled();
    expect(settings.state.count.data).toBeNull();
  });

  it("shows the service's preset window in the disabled editors and keeps it when switching to custom", async () => {
    const { api, settings } = store();
    await settings.show("p1");
    expect([settings.state.startInput, settings.state.endInput]).toEqual(["2026-10-18 08:30:00", "2026-10-18 09:30:00"]);
    await settings.setRange("4h");
    expect(api.exportCount).toHaveBeenLastCalledWith("p1", { range: "4h", formats: ["csv"] });
    expect(settings.state.startInput).toBe("2026-10-18 05:30:00");
    await settings.setRange("custom"); // EXP-050: the editors keep the last shown window and become editable
    expect(api.exportCount).toHaveBeenLastCalledWith("p1", {
      range: "custom",
      start: "2026-10-18T05:30:00",
      end: "2026-10-18T09:30:00",
      formats: ["csv"],
    });
  });

  it("recomputes a preset at every count (EXP-051, #12) and never moves a custom range", async () => {
    const api = settingsApi();
    let now = "2026-10-18T09:30:00";
    api.exportCount.mockImplementation(async (key: string, query: ExportCountQuery) => exportCount({ key, ...query, now }));
    const { settings } = store(api);
    await settings.show("p1");
    now = "2026-10-18T11:30:00";
    await settings.refreshCount();
    expect(settings.state.endInput).toBe("2026-10-18 11:30:00");
    await settings.setRange("custom");
    now = "2026-10-18T12:30:00";
    await settings.refreshCount();
    expect(settings.state.endInput).toBe("2026-10-18 11:30:00");
  });

  it("keeps a custom range when the export device changes and counts the new database (EXP-069, EXP-070)", async () => {
    const { api, settings } = store();
    await settings.show("p1");
    await settings.setRange("custom");
    settings.state.startInput = "2026-10-18 08:00:00";
    settings.state.endInput = "2026-10-18T09:00";
    await settings.applyCustom();
    await settings.selectExportDevice("p2");
    expect(api.exportCount).toHaveBeenLastCalledWith("p2", {
      range: "custom",
      start: "2026-10-18T08:00:00",
      end: "2026-10-18T09:00:00",
      formats: ["csv"],
    });
  });

  it("refuses an empty custom time without asking the service", async () => {
    const { api, settings } = store();
    await settings.show("p1");
    await settings.setRange("custom");
    const calls = api.exportCount.mock.calls.length;
    settings.state.startInput = "";
    expect(await settings.applyCustom()).toBe(false);
    expect(settings.state.inputError).toBe("请按“年-月-日 时:分:秒”（如 2026-10-27 08:00:00）填写开始时间和结束时间（北京时间）");
    expect(api.exportCount.mock.calls.length).toBe(calls);
  });

  it("counts files as records × formats; no format disables the export (EXP-011, EXP-014)", async () => {
    const { api, settings } = store();
    await settings.show("p1");
    await settings.setFormat("xlsx", true);
    expect(api.exportCount).toHaveBeenLastCalledWith("p1", { range: "1h", formats: ["csv", "xlsx"] });
    expect(settings.state.count.data?.files).toBe(6);
    await settings.setFormat("csv", false);
    await settings.setFormat("xlsx", false);
    expect(chosenFormats(settings.state)).toEqual([]);
    expect(settings.state.count.data?.can_export).toBe(false);
  });

  it("keeps the last count when a count fails and retries it (R-1-5)", async () => {
    const { api, settings } = store();
    await settings.show("p1");
    api.exportCount.mockRejectedValueOnce(unavailable());
    await settings.setRange("2h");
    expect(settings.state.count.error?.code).toBe("database_unavailable");
    expect(settings.state.count.data?.range.mode).toBe("1h");
    await settings.state.count.retry?.();
    expect(settings.state.count.error).toBeNull();
    expect(settings.state.count.data?.range.mode).toBe("2h");
  });

  it("an older page load that answers last never takes the status area back to its device (review #52 item 7)", async () => {
    const api = settingsApi();
    let release: () => void = () => {};
    api.settings.mockImplementationOnce(
      () => new Promise((resolve) => (release = () => resolve(settingsView(["p1", "p2"])))),
    );
    const { settings } = store(api);
    const first = settings.show("p1");
    await settings.show("p2");
    release();
    await first;
    await flushPromises();
    expect(settings.state.summaryKey).toBe("p2");
    expect(api.deviceSummary).toHaveBeenCalledTimes(1);
    expect(api.deviceSummary).toHaveBeenLastCalledWith("p2");
    expect(settings.state.summary.data?.device.key).toBe("p2");
  });

  it("retrying a first page load that failed restores the whole page (R-1-5; review #52 item 8)", async () => {
    const api = settingsApi();
    api.settings.mockRejectedValueOnce(unavailable());
    const { settings } = store(api);
    await settings.show("p2");
    expect(settings.state.view.error?.code).toBe("database_unavailable");
    expect(settings.state.exportKey).toBeNull();
    expect(api.exportCount).not.toHaveBeenCalled();
    expect(await settings.state.view.retry?.()).toBe(true);
    expect(settings.state.view.error).toBeNull();
    expect(settings.state.exportKey).toBe("p2"); // still the first visit: the viewed device (EXP-042)
    expect(settings.state.summaryKey).toBe("p2");
    expect(settings.state.summary.data?.device.key).toBe("p2");
    expect(api.exportCount).toHaveBeenLastCalledWith("p2", { range: "1h", formats: ["csv"] });
    expect(settings.state.count.data?.text).toBe("预计 3 条记录，将导出为 3 个文件");
  });

  it("a retry after the viewed device changed restores the page for the device viewed now", async () => {
    const api = settingsApi();
    api.settings.mockRejectedValueOnce(unavailable()).mockRejectedValueOnce(unavailable());
    const { settings } = store(api);
    await settings.show("p1");
    await settings.show("p2");
    expect(await settings.state.view.retry?.()).toBe(true);
    expect(settings.state.exportKey).toBe("p2");
    expect(settings.state.summaryKey).toBe("p2");
  });

  it("normalises an editor value to whole seconds", () => {
    expect(normaliseTime("2026-10-18T09:30")).toBe("2026-10-18T09:30:00");
    expect(normaliseTime("2026-10-18T09:30:05")).toBe("2026-10-18T09:30:05");
    expect(normaliseTime("2026-10-18T09:30:05.250")).toBe("2026-10-18T09:30:05");
    expect(normaliseTime("2026-10-18 09:30:05")).toBe("2026-10-18T09:30:05");
    expect(normaliseTime("bad")).toBeNull();
  });
});

describe("settings store: export (EXP-052, EXP-053, EXP-059, D-210)", () => {
  it("asks once with the service's confirmation, then exports exactly the confirmed range, database and count", async () => {
    const { api, settings } = store();
    await settings.show("p1");
    await settings.setFormat("xlsx", true);
    await settings.requestExport();
    const pending = settings.state.pending;
    expect(pending?.confirm?.title).toBe("确认导出");
    expect(api.exportAcquisitions).not.toHaveBeenCalled();
    await settings.confirmExport();
    expect(api.exportAcquisitions).toHaveBeenCalledWith("p1", {
      start: "2026-10-18T08:30:00",
      end: "2026-10-18T09:30:00",
      formats: ["csv", "xlsx"],
      snapshot_id: "p1-snap",
      records: pending?.confirm?.records,
    });
    expect(pending?.confirm?.records).toBeGreaterThan(0);
    expect(settings.state.pending).toBeNull();
    expect(settings.state.exporting.data?.text).toBe("已导出 3 个文件到：\n/alpha/exports");
  });

  it("cancelling the confirmation writes nothing", async () => {
    const { api, settings } = store();
    await settings.show("p1");
    await settings.requestExport();
    settings.cancelExport();
    expect(settings.state.pending).toBeNull();
    expect(api.exportAcquisitions).not.toHaveBeenCalled();
  });

  it("shows V1.0.3's notice instead of a confirmation", async () => {
    const api = settingsApi();
    api.exportCount.mockImplementation(async (key: string, query: ExportCountQuery) =>
      exportCount({ key, ...query, count: 0, notice: "所选时间范围内没有采集记录。" }),
    );
    const { settings } = store(api);
    await settings.show("p1");
    await settings.requestExport();
    expect(settings.state.pending).toBeNull();
    expect(settings.state.notice).toBe("所选时间范围内没有采集记录。");
    expect(api.exportAcquisitions).not.toHaveBeenCalled();
  });

  it("keeps the error of a failed export; exporting again is the retry (D-207, D-210)", async () => {
    const { api, settings } = store();
    await settings.show("p1");
    api.exportAcquisitions.mockRejectedValueOnce(
      new ApiError(500, { code: "export_failed", message: "导出失败", retryable: true, detail: "记录 ID 3 导出失败：\n…" }),
    );
    await settings.requestExport();
    await settings.confirmExport();
    expect(settings.state.exporting.error?.code).toBe("export_failed");
    expect(settings.state.count.data).not.toBeNull();
    await settings.requestExport();
    await settings.confirmExport();
    expect(settings.state.exporting.error).toBeNull();
    expect(api.exportAcquisitions).toHaveBeenCalledTimes(2);
  });

  it("re-reads the view and the count when the snapshot was replaced after the confirmation", async () => {
    const { api, settings } = store();
    await settings.show("p1");
    api.exportAcquisitions.mockRejectedValueOnce(
      new ApiError(409, { code: "snapshot_changed", message: "已导入新的快照", retryable: false, detail: null }),
    );
    await settings.requestExport();
    const views = api.settings.mock.calls.length;
    const counts = api.exportCount.mock.calls.length;
    await settings.confirmExport();
    expect(api.settings.mock.calls.length).toBe(views + 1);
    expect(api.exportCount.mock.calls.length).toBe(counts + 1);
    expect(settings.state.exporting.error?.code).toBe("snapshot_changed");
  });
});

describe("SettingsPage", () => {
  beforeEach(() => vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] }));
  afterEach(() => vi.useRealTimers());

  async function mounted(configured: string[] = ["p1", "p2"]) {
    const api = settingsApi(configured);
    const settings = createSettingsStore(api as unknown as ApiClient);
    await settings.show("p1");
    const wrapper = mount(SettingsPage, { props: { store: settings } });
    await flushPromises();
    return { api, settings, wrapper };
  }

  it("shows the configuration as read only and offers no write control (D-209)", async () => {
    const { wrapper } = await mounted();
    const text = wrapper.text();
    expect(text).toContain("只读快照不含配置");
    expect(wrapper.findAll("[data-role=bus] dd").map((item) => item.text())).toEqual(Array(7).fill(NO_CONFIG));
    const buttons = wrapper.findAll("button").map((button) => button.text());
    expect(buttons).toContain("导出采集记录");
    for (const forbidden of ["保存并应用全部配置", "设备维护", "选择…", "刷新串口", "退出维护并恢复采集"]) {
      expect(buttons).not.toContain(forbidden);
    }
    const rows = wrapper.findAll("[data-role=devices] tbody tr");
    expect(rows).toHaveLength(4);
    expect(rows[0]?.text()).toContain("设备1");
    expect(rows[0]?.attributes("title")).toContain("源库：");
    expect(rows[2]?.text()).toContain("未配置"); // UI-261
    expect(rows[2]?.classes()).toContain("unconfigured");
    expect(wrapper.find("[data-role=bus] input, [data-role=devices] input").exists()).toBe(false);
  });

  it("shows the status area of the viewed device with the serial number on hover (UI-080, UI-081)", async () => {
    const { wrapper } = await mounted();
    const status = wrapper.find("[data-role=status]");
    expect(status.text()).toContain("最近采集：2026-10-18 09:00:00.000 · 共 12 条");
    expect(status.text()).toContain("数据库：p1.sqlite3 · 文件大小：0.05 MB（导入时）");
    expect(status.find("[data-role=status-line]").attributes("title")).toBe("设备序列号：0x1234ABCD");
  });

  it("disables the preset times and enables them for 自定义时间 (EXP-071)", async () => {
    const { wrapper } = await mounted();
    const start = wrapper.find<HTMLInputElement>("input[name=export-start]");
    expect(start.element.disabled).toBe(true);
    expect(start.element.value).toBe("2026-10-18 08:30:00"); // V1.0.3 display format
    await wrapper.find("select[name=export-range]").setValue("custom");
    await flushPromises();
    expect(wrapper.find<HTMLInputElement>("input[name=export-start]").element.disabled).toBe(false);
  });

  it("refreshes the count every 3 seconds while shown (EXP-051) and stops when left", async () => {
    const { api, wrapper } = await mounted();
    const calls = api.exportCount.mock.calls.length;
    vi.advanceTimersByTime(3000);
    await flushPromises();
    expect(api.exportCount.mock.calls.length).toBe(calls + 1);
    wrapper.unmount();
    vi.advanceTimersByTime(9000);
    expect(api.exportCount.mock.calls.length).toBe(calls + 1);
  });

  it("the timer waits while the last status read is still under way (no pile-up of slow reads)", async () => {
    const { api } = await mounted();
    const reads = api.deviceSummary.mock.calls.length;
    let finish: () => void = () => undefined;
    api.deviceSummary.mockImplementationOnce(
      (key: string) => new Promise((resolve) => (finish = () => resolve(deviceSummary(key)))),
    );
    vi.advanceTimersByTime(3000); // starts a read that does not answer
    await flushPromises();
    vi.advanceTimersByTime(9000); // three more ticks while it is still loading
    await flushPromises();
    expect(api.deviceSummary.mock.calls.length).toBe(reads + 1);
    finish();
    await flushPromises();
    vi.advanceTimersByTime(3000);
    await flushPromises();
    expect(api.deviceSummary.mock.calls.length).toBe(reads + 2);
  });

  it("never rewrites a custom time while it is being typed; the timer counts the last applied range", async () => {
    const { api, wrapper, settings } = await mounted();
    await wrapper.find("select[name=export-range]").setValue("custom");
    await flushPromises();
    const start = wrapper.find<HTMLInputElement>("input[name=export-start]");
    const type = async (text: string) => {
      start.element.value = text; // keystrokes: input events only, no change event yet
      await start.trigger("input");
    };
    await type("2026-10-18 10:00");
    vi.advanceTimersByTime(3000);
    await flushPromises();
    expect(start.element.value).toBe("2026-10-18 10:00"); // not turned into 10:00:00 under the cursor
    expect(api.exportCount).toHaveBeenLastCalledWith("p1", {
      range: "custom",
      start: "2026-10-18T08:30:00",
      end: "2026-10-18T09:30:00",
      formats: ["csv"],
    });
    await type("2026-10-18 10:"); // half typed: no error line flashing on the timer
    vi.advanceTimersByTime(3000);
    await flushPromises();
    expect(settings.state.inputError).toBeNull();
    expect(start.element.value).toBe("2026-10-18 10:");
    await start.setValue("2026-10-18 09:00"); // input + change: committed, normalised and counted
    await flushPromises();
    expect(start.element.value).toBe("2026-10-18 09:00:00");
    expect(api.exportCount).toHaveBeenLastCalledWith("p1", expect.objectContaining({ start: "2026-10-18T09:00:00" }));
  });

  it("disables the export while the count of a newly chosen export device is still loading", async () => {
    const { api, wrapper, settings } = await mounted();
    expect(wrapper.find("[data-role=export-button]").attributes("disabled")).toBeUndefined();
    let release: () => void = () => undefined;
    api.exportCount.mockImplementationOnce(
      (key: string, query: ExportCountQuery) =>
        new Promise((resolve) => {
          release = () => resolve(exportCount({ key, ...query }));
        }),
    );
    const switching = settings.selectExportDevice("p2");
    await flushPromises();
    expect(settings.state.count.data?.device.key).toBe("p1"); // the last count is kept while loading (R-1-5)
    expect(wrapper.find("[data-role=export-button]").attributes("disabled")).toBeDefined();
    release();
    await switching;
    await flushPromises();
    expect(wrapper.find("[data-role=export-button]").attributes("disabled")).toBeUndefined();
  });

  it("confirms in a dialog with 是 / 否 and reports the result", async () => {
    const { api, wrapper } = await mounted();
    await wrapper.find("[data-role=export-button]").trigger("click");
    await flushPromises();
    const dialog = wrapper.find("[role=dialog]");
    expect(dialog.text()).toContain("导出设备：设备1");
    await dialog.find("[data-role=confirm-no]").trigger("click");
    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    expect(api.exportAcquisitions).not.toHaveBeenCalled();
    await wrapper.find("[data-role=export-button]").trigger("click");
    await flushPromises();
    await wrapper.find("[data-role=confirm-yes]").trigger("click");
    await flushPromises();
    expect(api.exportAcquisitions).toHaveBeenCalledTimes(1);
    expect(wrapper.find("[data-role=export-done]").text()).toContain("已导出 3 个文件到：");
  });

  it("disables the export button without records or formats (EXP-049)", async () => {
    const { wrapper, settings } = await mounted();
    expect(wrapper.find("[data-role=export-button]").attributes("disabled")).toBeUndefined();
    await settings.setFormat("csv", false);
    await flushPromises();
    expect(wrapper.find("[data-role=export-button]").attributes("disabled")).toBeDefined();
  });

  it("without snapshots says there is no export device", async () => {
    const { wrapper } = await mounted([]);
    expect(wrapper.find("[data-role=count]").text()).toBe("尚未配置导出设备");
  });

  it("keeps the last count on a failed refresh and offers a retry", async () => {
    const { api, wrapper, settings } = await mounted();
    api.exportCount.mockRejectedValueOnce(unavailable());
    await settings.refreshCount();
    await flushPromises();
    expect(wrapper.find("[role=alert]").text()).toContain("数据库不可访问");
    expect(wrapper.find("[data-role=count]").text()).toBe("预计 3 条记录，将导出为 3 个文件");
    await wrapper.find("[role=alert] button").trigger("click");
    await flushPromises();
    expect(wrapper.find("[role=alert]").exists()).toBe(false);
  });
});

describe("设备状态与最近日志 in tier 1 (API-16, issue #107)", () => {
  beforeEach(() => vi.useFakeTimers({ toFake: ["setInterval", "clearInterval"] }));
  afterEach(() => vi.useRealTimers());

  /** The tier the page reads from the takeover store; its other panels are stubbed. */
  function takeover(tier: number) {
    return { state: { tier: { data: { tier } } }, loadConfig: vi.fn(async () => true) };
  }

  async function mounted(tier = 1) {
    const api = settingsApi();
    const settings = createSettingsStore(api as unknown as ApiClient);
    await settings.show("p1");
    const wrapper = mount(SettingsPage, {
      props: { store: settings, takeover: takeover(tier) as never },
      global: { stubs: { TierPanel: true, AcquisitionConfigEditor: true, SettingsMaintenance: true } },
      attachTo: document.body,
    });
    await flushPromises();
    return { api, settings, wrapper };
  }

  it("the store reads the log with the summary of the viewed device and again on every tick", async () => {
    const { api, settings } = store();
    await settings.show("p2");
    expect(api.deviceLogs).toHaveBeenLastCalledWith("p2");
    expect(settings.state.logs.data?.device.key).toBe("p2");
    await settings.tick();
    expect(api.deviceLogs).toHaveBeenCalledTimes(2);
    expect(api.deviceSummary).toHaveBeenCalledTimes(2); // refresh_settings_console re-reads the summary too
  });

  it("keeps the last log when a read fails and retries it (R-1-5)", async () => {
    const { api, settings } = store();
    await settings.show("p1");
    api.deviceLogs.mockRejectedValueOnce(unavailable());
    await settings.tick();
    expect(settings.state.logs.error?.code).toBe("database_unavailable");
    expect(settings.state.logs.data?.items).toHaveLength(2);
    expect(await settings.state.logs.retry?.()).toBe(true);
    expect(settings.state.logs.error).toBeNull();
  });

  it("reads no log without a listed device (tier 0 lists none)", async () => {
    const api = settingsApi([]);
    const { settings } = store(api);
    await settings.show("p1");
    await settings.tick();
    expect(api.deviceLogs).not.toHaveBeenCalled();
    expect(settings.state.logs.data).toBeNull();
  });

  it("shows V1.0.3's status line, coloured, with the serial number on hover (UI-080, UI-081)", async () => {
    const { wrapper } = await mounted();
    const line = wrapper.get("[data-role=status-line]");
    expect(line.text()).toBe("设备1 · 在线 · 采集正常 · 曝光：正常");
    expect(line.attributes("title")).toBe("设备1\n设备序列号：0x1234ABCD");
    expect(line.classes()).toContain("tone-normal");
    expect(wrapper.text()).toContain("最近采集：2026-10-18 09:00:00.000 · 共 12 条");
    expect(wrapper.text()).not.toContain("alpha 只读版不显示");
    wrapper.unmount();
  });

  it("lists the log as 时间 / 类别 / 结果, errors in red, full text on hover (UI-078, UI-279, UI-280)", async () => {
    const { wrapper } = await mounted();
    const table = wrapper.get("[data-role=log]");
    expect(table.findAll("th").map((cell) => cell.text())).toEqual(["时间", "类别", "结果"]);
    const rows = table.findAll("tbody tr");
    expect(rows.map((row) => row.findAll("td").map((cell) => cell.text()))).toEqual([
      ["2026-10-18 09:01:00.000", "通信异常", "设备无应答"],
      ["2026-10-18 09:00:00.000", "连接", "总线已连接"],
    ]);
    expect(rows[0]?.classes()).toContain("error");
    expect(rows[1]?.classes()).not.toContain("error");
    expect(rows[0]?.findAll("td")[1]?.attributes("title")).toBe("通信异常\ncommunication");
    wrapper.unmount();
  });

  it("opens 日志详情 on a double-click with the row's snapshot; a refresh does not change it (UI-100..104)", async () => {
    const { api, wrapper } = await mounted();
    const writeText = vi.fn(async () => undefined);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    await wrapper.findAll("[data-role=log] tbody tr")[0]?.trigger("dblclick");
    const dialog = wrapper.get("[data-role=log-details]");
    expect(dialog.get("h2").text()).toBe("日志详情");
    const text = dialog.get("[data-role=log-details-text]").text();
    expect(text).toContain("类别：通信异常（communication）");
    expect(text).toContain("消息：\n设备无应答");
    api.deviceLogs.mockResolvedValue({ ...deviceLog("p1"), items: [] });
    vi.advanceTimersByTime(3000);
    await flushPromises();
    expect(wrapper.findAll("[data-role=log] tbody tr")).toHaveLength(0);
    expect(wrapper.get("[data-role=log-details-text]").text()).toBe(text); // UI-102: the snapshot stays
    await wrapper.get("[data-role=log-copy]").trigger("click");
    await flushPromises();
    expect(writeText).toHaveBeenCalledWith(deviceLog("p1").items[0]?.details_text); // UI-103
    await wrapper.get("[data-role=log-close]").trigger("click");
    expect(wrapper.find("[data-role=log-details]").exists()).toBe(false);
    wrapper.unmount();
  });

  it("says when copying failed instead of failing silently", async () => {
    const { wrapper } = await mounted();
    Object.defineProperty(navigator, "clipboard", {
      value: { writeText: vi.fn(async () => Promise.reject(new Error("denied"))) },
      configurable: true,
    });
    await wrapper.findAll("[data-role=log] tbody tr")[1]?.trigger("dblclick");
    await wrapper.get("[data-role=log-copy]").trigger("click");
    await flushPromises();
    expect(wrapper.get("[data-role=log-details] [role=alert]").text()).toContain("复制失败");
    wrapper.unmount();
  });

  it("keeps the shown log and offers a retry when a refresh fails", async () => {
    const { api, wrapper } = await mounted();
    api.deviceLogs.mockRejectedValueOnce(unavailable());
    vi.advanceTimersByTime(3000);
    await flushPromises();
    expect(wrapper.findAll("[data-role=log] tbody tr")).toHaveLength(2);
    expect(wrapper.text()).toContain("仍显示上次读取的状态与日志");
    wrapper.unmount();
  });

  it("tier 0 is unchanged: no log table, the old note", async () => {
    const { wrapper } = await mounted(0);
    expect(wrapper.find("[data-role=log]").exists()).toBe(false);
    expect(wrapper.text()).toContain("只读模式不连接设备，不显示设备日志与通信状态。");
    wrapper.unmount();
  });
});

describe("App: the settings tab", () => {
  it("is the last tab below tier 2 (UI-124 order) and shows the read-only page", async () => {
    const offered = PAGES.filter((item) => (item.tier ?? 0) < 2).map((item) => item.label);
    expect(offered).toEqual(["实时概览", "历史回放", "光谱计算", "光积累计算", "设置与导出"]);
    expect(PAGES.at(-1)).toMatchObject({ label: "设备维护", tier: 2 }); // 17_ section 2: tier 2 only
    const fetchImpl = vi.fn(async (input: string) => {
      const path = new URL(input, "http://127.0.0.1").pathname;
      if (path.endsWith("/health")) return jsonResponse(200, health());
      if (path.endsWith("/snapshots")) return jsonResponse(200, snapshots());
      if (path.endsWith("/devices")) return jsonResponse(200, devices(["p1"]));
      if (path.endsWith("/acquisitions")) return jsonResponse(200, page([]));
      if (path.endsWith("/settings")) return jsonResponse(200, settingsView(["p1"]));
      if (path.endsWith("/summary")) return jsonResponse(200, deviceSummary("p1"));
      if (path.endsWith("/export/count")) {
        const params = new URL(input, "http://127.0.0.1").searchParams;
        return jsonResponse(
          200,
          exportCount({ key: "p1", range: params.get("range") ?? "1h", formats: params.getAll("formats") as ExportKind[] }),
        );
      }
      return jsonResponse(404, { error: { code: "not_found", message: path, retryable: false, detail: null } });
    });
    const client = new ApiClient("t", fetchImpl as unknown as typeof fetch);
    const wrapper = mount(App, {
      props: {
        store: createHistoryStore(client),
        dli: createDliStore(client),
        calc: createCalcStore(client),
        settings: createSettingsStore(client),
        overview: createOverviewStore(client),
        initialView: "settings",
      },
      global: { stubs: { SpectrumChart: true } },
    });
    await flushPromises();
    await flushPromises();
    expect(wrapper.find("[data-role=count]").text()).toBe("预计 3 条记录，将导出为 3 个文件");
    expect(wrapper.find(".tab.active").text()).toBe("设置与导出");
    wrapper.unmount();
  });
});
