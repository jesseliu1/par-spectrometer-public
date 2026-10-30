/**
 * 导出诊断包 and 维护记录 on 设置与导出 (D-226; API-27, API-28): client paths, the store (filters, kept data on
 * failure, the filter's device list) and the panel (table, result colours by class, problems, empty states, export
 * result and retry).
 */
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError, type Fetch } from "../src/api/client";
import type { DiagnosticsExported, MaintenanceLog, MaintenanceLogItem, MaintenanceLogQuery } from "../src/api/types";
import SupportPanel from "../src/components/SupportPanel.vue";
import { createSupportStore } from "../src/pages/supportStore";
import { jsonResponse } from "./fixtures";

const TEXTS = {
  title: "维护记录",
  note: "只读：来自 alpha 设备库……",
  columns: ["时间", "设备", "类型", "写入前", "写入值", "回读", "结果", "说明"],
  empty_text: "没有设备写入记录",
  no_devices_text: "alpha 的档位 1 配置中还没有设备",
  time_sync_label: "包含设备对时（每台设备每小时一次）",
  limit_text: "只显示最新 200 条",
  scan_limited_text: "只扫描了每台设备最新 100000 条设备日志，更早记录未扫描",
};

function item(overrides: Partial<MaintenanceLogItem> = {}): MaintenanceLogItem {
  return {
    device_key: "p1",
    device_name: "North",
    occurred_at: "2026-10-19T09:01:00.000",
    occurred_at_text: "2026-10-19 09:01:00.000",
    kind: "calibration_write",
    kind_text: "校准写入",
    before_text: "x_min=350, y1=-0.0123",
    after_text: "x_min=350, y1=-0.015",
    readback_text: "x_min=350, y1=-0.015",
    result: "success",
    result_text: "成功",
    detail: "写入并回读光谱仪校准（状态码 3，错误码 0）",
    source: "calibration_audit #2",
    ...overrides,
  };
}

function maintenanceLog(items: MaintenanceLogItem[], overrides: Partial<MaintenanceLog> = {}): MaintenanceLog {
  return {
    as_of: "2026-10-19T09:30:00.000",
    devices: [
      { key: "p1", position: 1, name: "North", database_name: "North.sqlite3", state: "ok", problem: null },
      { key: "p2", position: 2, name: "South", database_name: "South.sqlite3", state: "ok", problem: null },
    ],
    items,
    limit: 200,
    limit_reached: false,
    time_sync: false,
    scan_limited: false,
    texts: TEXTS,
    ...overrides,
  };
}

const exported: DiagnosticsExported = {
  as_of: "2026-10-19T09:30:00.000",
  path: "/alpha/exports/diagnostics/PAR_diagnostics_20261019_093000.zip",
  directory: "/alpha/exports/diagnostics",
  file_name: "PAR_diagnostics_20261019_093000.zip",
  size: 1234,
  files: ["README.txt"],
  problems: [],
  text: "已保存诊断包：/alpha/exports/diagnostics/PAR_diagnostics_20261019_093000.zip\n共 20 个文件。",
};

const pending = item({
  kind: "comm_write",
  kind_text: "通信参数写入",
  before_text: "地址 1 · COM7 · 9600 bps · 无校验",
  after_text: "地址 7 · COM7 · 9600 bps · 无校验",
  readback_text: "未记录",
  result: "pending",
  result_text: "待核对",
  occurred_at_text: "2026-10-19 09:04:00.000",
  source: "diagnostics #9",
});
const failed = item({ result: "failure", result_text: "失败", source: "diagnostics #3", before_text: "未记录" });

function fakeApi(log = maintenanceLog([pending, failed, item()])) {
  return {
    maintenanceLog: vi.fn(async (_query: MaintenanceLogQuery) => log),
    exportDiagnostics: vi.fn(async () => exported),
  };
}

const unavailable = () =>
  new ApiError(503, { code: "database_unavailable", message: "数据库不可访问", retryable: true, detail: null });

describe("ApiClient support paths", () => {
  it("asks the log with the device and time-sync filters, and posts the bundle export", async () => {
    const calls: string[] = [];
    const fetchImpl: Fetch = async (url, init) => {
      calls.push(`${init?.method ?? "GET"} ${url}`);
      return jsonResponse(200, {});
    };
    const api = new ApiClient("t", fetchImpl);
    await api.maintenanceLog({ device: null, timeSync: false });
    await api.maintenanceLog({ device: "p2", timeSync: true });
    await api.exportDiagnostics();
    expect(calls).toEqual([
      "GET /api/v0/support/maintenance-log",
      "GET /api/v0/support/maintenance-log?device=p2&time_sync=true",
      "POST /api/v0/support/diagnostics-bundle",
    ]);
  });
});

describe("support store", () => {
  it("filters by device and time sync, and keeps the filter's devices from the last read of all devices", async () => {
    const api = fakeApi();
    const store = createSupportStore(api as unknown as ApiClient);
    await store.loadLog();
    expect(api.maintenanceLog).toHaveBeenLastCalledWith({ device: null, timeSync: false });
    expect(store.state.devices.map((device) => device.key)).toEqual(["p1", "p2"]);
    api.maintenanceLog.mockResolvedValueOnce(maintenanceLog([item()], { devices: [maintenanceLog([]).devices[0]!] }));
    await store.setDevice("p1");
    expect(api.maintenanceLog).toHaveBeenLastCalledWith({ device: "p1", timeSync: false });
    expect(store.state.devices.map((device) => device.key)).toEqual(["p1", "p2"]); // still both choices
    await store.setTimeSync(true);
    expect(api.maintenanceLog).toHaveBeenLastCalledWith({ device: "p1", timeSync: true });
  });

  it("keeps the last list when a read fails, with a retry (R-1-5)", async () => {
    const api = fakeApi();
    const store = createSupportStore(api as unknown as ApiClient);
    await store.loadLog();
    api.maintenanceLog.mockRejectedValueOnce(unavailable());
    expect(await store.loadLog()).toBe(false);
    expect(store.state.log.error?.code).toBe("database_unavailable");
    expect(store.state.log.data?.items).toHaveLength(3);
    expect(await store.state.log.retry?.()).toBe(true);
    expect(store.state.log.error).toBeNull();
  });
});

describe("SupportPanel", () => {
  it("shows every write newest first with before, written value, readback and result", async () => {
    const store = createSupportStore(fakeApi() as unknown as ApiClient);
    const wrapper = mount(SupportPanel, { props: { store } });
    await flushPromises();
    const headers = wrapper.findAll("[data-role=log-table] th").map((cell) => cell.text());
    expect(headers).toEqual(TEXTS.columns);
    const rows = wrapper.findAll("[data-role=log-table] tbody tr");
    expect(rows).toHaveLength(3);
    expect(rows[0]!.findAll("td").map((cell) => cell.text())).toEqual([
      "2026-10-19 09:04:00.000",
      "North",
      "通信参数写入",
      "地址 1 · COM7 · 9600 bps · 无校验",
      "地址 7 · COM7 · 9600 bps · 无校验",
      "未记录",
      "待核对",
      "写入并回读光谱仪校准（状态码 3，错误码 0）",
    ]);
    const results = wrapper.findAll("[data-role=log-result]");
    expect(results.map((cell) => cell.classes())).toEqual([["nowrap", "result-pending"], ["nowrap", "result-failure"], ["nowrap", "result-success"]]);
    expect(wrapper.find("[data-role=log-empty]").exists()).toBe(false);
  });

  it("names a database that could not be read, and says when nothing is registered or recorded", async () => {
    const problem = maintenanceLog([], {
      devices: [{ key: "p2", position: 2, name: "South", database_name: "South.sqlite3", state: "unavailable", problem: "数据库不可访问" }],
    });
    const store = createSupportStore(fakeApi(problem) as unknown as ApiClient);
    const wrapper = mount(SupportPanel, { props: { store } });
    await flushPromises();
    expect(wrapper.find("[data-role=log-problems]").text()).toBe("South（South.sqlite3）：数据库不可访问");
    expect(wrapper.find("[data-role=log-empty]").text()).toBe("没有设备写入记录");

    const none = createSupportStore(fakeApi(maintenanceLog([], { devices: [] })) as unknown as ApiClient);
    const empty = mount(SupportPanel, { props: { store: none } });
    await flushPromises();
    expect(empty.find("[data-role=log-no-devices]").text()).toContain("还没有设备");
    expect(empty.find("select[name=log-device]").attributes("disabled")).toBeDefined();
  });

  it("exports the bundle and shows the service's text; a failure offers a retry", async () => {
    const api = fakeApi();
    api.exportDiagnostics.mockRejectedValueOnce(
      new ApiError(500, { code: "export_failed", message: "诊断包导出失败", retryable: true, detail: "保存目录：/alpha" }),
    );
    const store = createSupportStore(api as unknown as ApiClient);
    const wrapper = mount(SupportPanel, { props: { store } });
    await flushPromises();
    await wrapper.find("[data-role=diagnostics-export]").trigger("click");
    await flushPromises();
    expect(wrapper.find("[role=alert]").text()).toContain("诊断包导出失败");
    expect(wrapper.find("[data-role=diagnostics-done]").exists()).toBe(false);
    await wrapper.find("[role=alert] button").trigger("click");
    await flushPromises();
    expect(api.exportDiagnostics).toHaveBeenCalledTimes(2);
    expect(wrapper.find("[data-role=diagnostics-done]").text()).toContain("已保存诊断包：");
  });

  it("shows the limit note and the time-sync choice from the service", async () => {
    const store = createSupportStore(fakeApi(maintenanceLog([item()], { limit_reached: true })) as unknown as ApiClient);
    const wrapper = mount(SupportPanel, { props: { store } });
    await flushPromises();
    expect(wrapper.find("[data-role=log-limit]").text()).toBe("只显示最新 200 条");
    expect(wrapper.find("label.choice").text()).toBe(TEXTS.time_sync_label);
    await wrapper.find("input[name=log-time-sync]").setValue(true);
    await flushPromises();
    expect(store.state.timeSync).toBe(true);
  });
});

describe("SupportPanel failures (PR #63 reviews)", () => {
  it("a device whose database cannot be read answers 503: the error shows with a retry and the last rows stay", async () => {
    const api = fakeApi();
    const store = createSupportStore(api as unknown as ApiClient);
    const wrapper = mount(SupportPanel, { props: { store } });
    await flushPromises();
    expect(wrapper.findAll("[data-role=log-table] tbody tr")).toHaveLength(3);
    api.maintenanceLog.mockRejectedValueOnce(unavailable());
    await wrapper.find("select[name=log-device]").setValue("p2");
    await flushPromises();
    expect(api.maintenanceLog).toHaveBeenLastCalledWith({ device: "p2", timeSync: false });
    expect(wrapper.find("[role=alert]").text()).toContain("数据库不可访问");
    expect(wrapper.findAll("[data-role=log-table] tbody tr")).toHaveLength(3);
    await wrapper.find("[role=alert] button").trigger("click");
    await flushPromises();
    expect(api.maintenanceLog).toHaveBeenLastCalledWith({ device: "p2", timeSync: false });
    expect(wrapper.find("[role=alert]").exists()).toBe(false);
  });

  it("labels the time-sync choice even when the first read fails", async () => {
    const api = fakeApi();
    api.maintenanceLog.mockRejectedValueOnce(unavailable());
    const wrapper = mount(SupportPanel, { props: { store: createSupportStore(api as unknown as ApiClient) } });
    await flushPromises();
    expect(wrapper.find("[role=alert]").exists()).toBe(true);
    expect(wrapper.find("label.choice").text()).toBe("包含设备对时");
  });
});

describe("SupportPanel scan window (PR #63 re-review item 2)", () => {
  it("says when older device-log rows were not scanned, and only then", async () => {
    const limited = createSupportStore(fakeApi(maintenanceLog([item()], { scan_limited: true })) as unknown as ApiClient);
    const wrapper = mount(SupportPanel, { props: { store: limited } });
    await flushPromises();
    expect(wrapper.find("[data-role=log-scan-limited]").text()).toBe(TEXTS.scan_limited_text);
    const full = mount(SupportPanel, { props: { store: createSupportStore(fakeApi() as unknown as ApiClient) } });
    await flushPromises();
    expect(full.find("[data-role=log-scan-limited]").exists()).toBe(false);
  });
});
