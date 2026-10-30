/**
 * Tier 2 "设备维护" page (17_ 10.5): the page renders the service's view model and computes nothing; every write is two
 * steps (the service's confirmation text first, then the write with that id; 否 sends nothing); a failed request keeps
 * the last valid view with 重试; the halt comes first and nothing offers to clear it; the tab exists only in tier 2.
 */
import { flushPromises, mount } from "@vue/test-utils";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { ApiClient } from "../src/api/client";
import type { MaintenanceState, WriteConfirmation } from "../src/api/types";
import MaintenanceCalibration from "../src/components/MaintenanceCalibration.vue";
import PageNav from "../src/components/PageNav.vue";
import SettingsMaintenance from "../src/components/SettingsMaintenance.vue";
import MaintenancePage from "../src/pages/MaintenancePage.vue";
import { createMaintenanceStore } from "../src/pages/maintenanceStore";
import type { TakeoverStore } from "../src/pages/takeoverStore";

vi.mock("echarts/core", () => ({
  use: () => undefined,
  init: () => ({
    setOption: () => undefined,
    resize: () => undefined,
    dispose: () => undefined,
    getZr: () => ({ on: () => undefined }),
  }),
}));

const FIELDS = ["x_min", "x_max", "x1", "x2", "x3", "y0", "y1", "y2", "y3", "y4", "k_global", "limit_min", "limit_max"];

function view(overrides: Partial<MaintenanceState> = {}): MaintenanceState {
  return {
    available: true,
    reason: "",
    version: 3,
    session: true,
    tab: 0,
    maintenance: false,
    entering: false,
    halt: null,
    busy: false,
    devices: [
      { key: "North", label: "North", position: "p1" },
      { key: "South", label: "South（停用）", position: "p2" },
    ],
    target: "North",
    target_locked: false,
    header: { address: "地址：1", communication: "通信：在线", state: "正常采集", state_level: "ok" },
    diagnostics: {
      stamp: "诊断快照时间：2026-10-18 09:30:00",
      identity: "设备身份：PAR-FAKE    序列号：305419896 (0x12345678)    类型：3",
      values: "MCU 温度：31.50 ℃    初始化：完成    需要重新上电：否",
      exposure: "曝光：正常    曝光模式：手动    曝光时间：20.0 ms",
      data: "原始数据：有效    计算数据：有效",
      has_snapshot: true,
      historical: false,
      rows: [
        { category: "通信", name: "通信改参超时", count: "0", delta: "0", zero: true, tooltip: "" },
        { category: "通信", name: "CRC 错误", count: "2", delta: "—", zero: false, tooltip: "首次读取…" },
      ],
      empty_text: "未发现非零错误计数",
      refresh_enabled: true,
      read_reason: "",
      export_text: "导出诊断快照",
      export_enabled: true,
      events: [{ time: "2026-10-18 09:30:00", level: "信息", operation: "读取设备诊断", message: "已读取设备维护诊断", details: "{}" }],
    },
    calibration: {
      fields: FIELDS.map((name) => ({ name, caption: "", decimals: 2, text: "1.00", minimum: -1e8, maximum: 1e8, enabled: true })),
      read_enabled: true,
      write_enabled: true,
      discard_enabled: false,
      editable: true,
      dirty: false,
      version: 4,
      value_state: "",
      value_state_error: false,
      history: false,
      note: "",
      note_error: false,
      status: "校准状态：已校准",
      status_tooltip: "",
      error: "错误状态：无错误",
      error_tooltip: "",
      version_text: "版本 / 节点数：v1 / 5",
      time: "2025-10-09 16:53:20",
      curve: null,
      out_of_order: false,
      out_of_order_text: "节点波长须递增",
      unavailable_reason: "",
    },
    communication: {
      enter_visible: true,
      enter_enabled: true,
      state: "未进入通信维护；正常采集",
      attention: false,
      busy: false,
      form_enabled: false,
      isolation_enabled: false,
      isolated: false,
      read_enabled: false,
      write_enabled: false,
      verify_enabled: false,
      pending: false,
      form: {
        serial_port: "COM7",
        old: { slave_id: 1, baudrate: 19200, parity: "N" },
        new: { slave_id: 1, baudrate: 19200, parity: "N" },
      },
      form_locked: false,
      identity: ["设备身份：未读取"],
      target: "维护目标：North（登记地址 1）",
      fixed_parameters: "数据位 / 停止位：8 / 1（固定）",
      baudrates: [9600, 19200],
      parities: [{ value: "N", label: "无校验 N" }],
    },
    footer: {
      resume_visible: false,
      resume_enabled: false,
      resume_reason: "",
      close_text: "关闭",
      close_enabled: true,
      result: "",
      result_error: false,
      exported_file: null,
    },
    notice: null,
    settings: {},
    ...overrides,
  };
}

function confirmation(text: string): WriteConfirmation {
  return { confirmation_id: "once", action: "enter", expires_at: "2026-10-18T09:31:00", title: "停止全部采集并进入维护", text };
}

interface Call {
  method: string;
  path: string;
  body: unknown;
}

function service(current: () => MaintenanceState, fail: Set<string> = new Set()) {
  const calls: Call[] = [];
  const fetchImpl = vi.fn(async (input: string, init?: RequestInit) => {
    const url = new URL(input, "http://127.0.0.1");
    const path = url.pathname.replace("/api/v0", "") + url.search;
    const body = init?.body ? JSON.parse(String(init.body)) : undefined;
    calls.push({ method: init?.method ?? "GET", path, body });
    if (fail.has(path)) {
      return new Response(JSON.stringify({ error: { code: "precondition_failed", message: "设备未登记或已停用。", retryable: true, detail: null } }), { status: 409 });
    }
    if (path.endsWith("/confirmations")) return new Response(JSON.stringify(confirmation("将等待当前通信结束，……是否继续？")), { status: 201 });
    return new Response(JSON.stringify(current()), { status: 200 });
  });
  return { api: new ApiClient("t", fetchImpl), calls };
}

describe("maintenance page", () => {
  it("renders the service's header, tabs and diagnostics without computing anything", async () => {
    const { api } = service(() => view());
    const store = createMaintenanceStore(api);
    const wrapper = mount(MaintenancePage, { props: { store } });
    await flushPromises();
    expect(wrapper.find("[data-role=maintenance-state]").text()).toBe("正常采集");
    expect(wrapper.findAll(".tabs .tab").map((tab) => tab.text())).toEqual(["设备状态与诊断", "光谱校准", "通信参数维护"]);
    expect(wrapper.find("[data-role=diagnostics-identity]").text()).toContain("0x12345678");
    // 仅显示非零项 (on by default, as V1.0.3): the zero row is hidden, the other shows the service's increment text
    const rows = wrapper.findAll("[data-role=diagnostics-errors] tbody tr");
    expect(rows).toHaveLength(1);
    expect(rows[0]!.text()).toContain("CRC 错误");
    expect(wrapper.find("[data-role=maintenance-leave]").exists()).toBe(false); // only in maintenance
  });

  it("asks with the service's text first: 否 sends nothing, 是 sends the write with the confirmation id", async () => {
    const { api, calls } = service(() => view({ tab: 2 }));
    const store = createMaintenanceStore(api);
    const wrapper = mount(MaintenancePage, { props: { store } });
    await flushPromises();
    await wrapper.find("[data-role=maintenance-enter]").trigger("click");
    await flushPromises();
    expect(wrapper.find("[role=dialog]").text()).toContain("将等待当前通信结束");
    await wrapper.find("[data-role=confirm-no]").trigger("click");
    await flushPromises();
    expect(calls.filter((call) => call.path === "/maintenance/enter")).toEqual([]);
    await wrapper.find("[data-role=maintenance-enter]").trigger("click");
    await flushPromises();
    await wrapper.find("[data-role=confirm-yes]").trigger("click");
    await flushPromises();
    expect(calls.filter((call) => call.path === "/maintenance/enter")).toEqual([
      { method: "POST", path: "/maintenance/enter", body: { confirmation_id: "once" } },
    ]);
  });

  it("keeps the last view and offers 重试 when an action is refused", async () => {
    const { api } = service(() => view(), new Set(["/maintenance/diagnostics/read"]));
    const store = createMaintenanceStore(api);
    const wrapper = mount(MaintenancePage, { props: { store } });
    await flushPromises();
    await wrapper.find("[data-role=diagnostics-refresh]").trigger("click");
    await flushPromises();
    expect(wrapper.find("[role=alert]").text()).toContain("设备未登记或已停用。");
    expect(wrapper.find("[role=alert] button").text()).toBe("重试");
    expect(wrapper.find("[data-role=diagnostics-identity]").text()).toContain("0x12345678"); // still shown
  });

  it("shows the halt first and has no control that clears it", async () => {
    const message = "采集停止中：North（地址 1）探头要求重新上电；所有设备的后台采集已停止";
    const halted = view({
      halt: { message },
      header: { address: "地址：1", communication: "通信：硬件异常停止", state: message, state_level: "error" },
    });
    const { api } = service(() => halted);
    const store = createMaintenanceStore(api);
    const wrapper = mount(MaintenancePage, { props: { store } });
    await flushPromises();
    expect(wrapper.find("[data-role=maintenance-halt]").text()).toContain(message);
    expect(wrapper.find("[data-role=maintenance-state]").classes()).toContain("error");
    const labels = wrapper.findAll("button").map((button) => button.text());
    expect(labels.filter((label) => /清除|解除|复位|reset/i.test(label))).toEqual([]);
  });

  it("sends a committed field as typed; the service rounds and answers", async () => {
    const wrapper = mount(MaintenanceCalibration, { props: { calibration: view().calibration!, busy: false } });
    const input = wrapper.find("input[name=calibration-y1]");
    await input.setValue("-1.234");
    expect(wrapper.emitted("edit")).toEqual([["y1", -1.234]]);
  });

  it("does not overwrite what is being typed when the service's view refreshes", async () => {
    const calibration = view().calibration!;
    const wrapper = mount(MaintenanceCalibration, { props: { calibration, busy: false } });
    const input = wrapper.find("input[name=calibration-y2]");
    (input.element as HTMLInputElement).value = "3.2";
    await input.trigger("input");
    await wrapper.setProps({ calibration: { ...calibration, version: 5 } }); // an event arrived meanwhile
    expect((wrapper.find("input[name=calibration-y2]").element as HTMLInputElement).value).toBe("3.2");
    expect(wrapper.emitted("edit")).toBeUndefined();
  });

  it.each([true, false])(
    "follows a pending write in the communication form; the declaration shows its kept tick (%s), disabled (D-218)",
    async (kept) => {
      const pending = view({ tab: 2, maintenance: true });
      pending.communication = {
        ...pending.communication!,
        enter_visible: false,
        pending: true,
        form_locked: true,
        isolation_enabled: false,
        isolated: kept,
        verify_enabled: true,
        form: { serial_port: "COM9", old: { slave_id: 1, baudrate: 19200, parity: "N" }, new: { slave_id: 7, baudrate: 9600, parity: "N" } },
      };
      const { api, calls } = service(() => pending);
      const store = createMaintenanceStore(api);
      store.state.form.isolated = !kept; // whatever this browser had: the service's window state wins
      const wrapper = mount(MaintenancePage, { props: { store } });
      await flushPromises();
      expect(store.state.form.new.slave_id).toBe(7);
      expect(wrapper.find("input[name=maintenance-port]").attributes("disabled")).toBeDefined();
      const box = wrapper.find("input[name=maintenance-isolated]");
      expect(box.attributes("disabled")).toBeDefined();
      expect((box.element as HTMLInputElement).checked).toBe(kept);
      await wrapper.find("[data-role=comm-verify]").trigger("click");
      await flushPromises();
      const verify = calls.find((call) => call.path === "/maintenance/comm/verify");
      expect(verify?.body).toMatchObject({ serial_port: "COM9", new: { slave_id: 7 }, isolated: kept });
    },
  );
});

/** The communication tab in maintenance with the fields open (the state after 读取连接参数 is possible). */
function inMaintenance(overrides: Partial<NonNullable<MaintenanceState["communication"]>> = {}): MaintenanceState {
  const base = view({ tab: 2, maintenance: true });
  base.communication = {
    ...base.communication!,
    enter_visible: false,
    form_enabled: true,
    isolation_enabled: true,
    read_enabled: true,
    write_enabled: true,
    verify_enabled: false,
    ...overrides,
  };
  base.footer = { ...base.footer!, resume_visible: true, resume_enabled: true };
  return base;
}

describe("maintenance page follows the service (PR #55 review M3)", () => {
  it("sends the isolation declaration exactly as ticked (F8)", async () => {
    const { api, calls } = service(() => inMaintenance());
    const store = createMaintenanceStore(api);
    const wrapper = mount(MaintenancePage, { props: { store } });
    await flushPromises();
    await wrapper.find("[data-role=comm-read]").trigger("click");
    await flushPromises();
    await wrapper.find("input[name=maintenance-isolated]").setValue(true);
    await wrapper.find("[data-role=comm-read]").trigger("click");
    await flushPromises();
    const reads = calls.filter((call) => call.path === "/maintenance/comm/read");
    expect(reads.map((call) => (call.body as { isolated: boolean }).isolated)).toEqual([false, true]);
  });

  it("clears the isolation declaration when the maintenance device changes (F6)", async () => {
    let current = inMaintenance();
    const { api, calls } = service(() => current);
    const store = createMaintenanceStore(api);
    const wrapper = mount(MaintenancePage, { props: { store } });
    await flushPromises();
    await wrapper.find("input[name=maintenance-isolated]").setValue(true);
    current = { ...inMaintenance(), target: "South" };
    await store.load();
    await flushPromises();
    expect(store.state.form.isolated).toBe(false);
    await wrapper.find("[data-role=comm-read]").trigger("click");
    await flushPromises();
    expect(calls.filter((call) => call.path === "/maintenance/comm/read").at(-1)?.body).toMatchObject({ isolated: false });
  });

  it("asks before re-reading the calibration over unwritten edits (F4)", async () => {
    const dirty = view({ tab: 1 });
    dirty.calibration = { ...dirty.calibration!, dirty: true, discard_enabled: true };
    const { api, calls } = service(() => dirty);
    const store = createMaintenanceStore(api);
    const wrapper = mount(MaintenancePage, { props: { store } });
    await flushPromises();
    await wrapper.find("[data-role=calibration-read]").trigger("click");
    await flushPromises();
    expect(calls.filter((call) => call.path === "/maintenance/calibration/read")).toEqual([]);
    expect(calls.filter((call) => call.path === "/maintenance/calibration/read/confirmations")).toHaveLength(1);
    await wrapper.find("[data-role=confirm-yes]").trigger("click");
    await flushPromises();
    expect(calls.filter((call) => call.path === "/maintenance/calibration/read")).toEqual([
      { method: "POST", path: "/maintenance/calibration/read", body: { confirmation_id: "once" } },
    ]);
  });

  it("asks before closing over unwritten edits, and closes with the confirmation id (F5)", async () => {
    const dirty = view({ tab: 1 });
    dirty.calibration = { ...dirty.calibration!, dirty: true, discard_enabled: true };
    const { api, calls } = service(() => dirty);
    const store = createMaintenanceStore(api);
    const wrapper = mount(MaintenancePage, { props: { store } });
    await flushPromises();
    await wrapper.find("[data-role=maintenance-close]").trigger("click");
    await flushPromises();
    expect(calls.filter((call) => call.method === "DELETE")).toEqual([]);
    expect(calls.filter((call) => call.path === "/maintenance/page/close/confirmations")).toHaveLength(1);
    await wrapper.find("[data-role=confirm-yes]").trigger("click");
    await flushPromises();
    expect(calls.filter((call) => call.method === "DELETE").map((call) => call.path)).toEqual([
      "/maintenance/page?confirmation_id=once",
    ]);
  });

  it.each([
    ["comm-write", "write_enabled"],
    ["comm-verify", "verify_enabled"],
    ["comm-read", "read_enabled"],
  ] as const)("enables %s only as the service's %s says (F9, F14)", async (role, flag) => {
    for (const enabled of [false, true]) {
      const { api } = service(() => inMaintenance({ [flag]: enabled }));
      const store = createMaintenanceStore(api);
      const wrapper = mount(MaintenancePage, { props: { store } });
      await flushPromises();
      expect(wrapper.find(`[data-role=${role}]`).attributes("disabled") === undefined).toBe(enabled);
      wrapper.unmount();
    }
  });

  it("enables 退出通信维护并恢复采集 only as the service's resume_enabled says (F10)", async () => {
    for (const enabled of [false, true]) {
      const current = inMaintenance();
      current.footer = { ...current.footer!, resume_enabled: enabled, resume_reason: enabled ? "" : "校准修改未处理" };
      const { api } = service(() => current);
      const store = createMaintenanceStore(api);
      const wrapper = mount(MaintenancePage, { props: { store } });
      await flushPromises();
      expect(wrapper.find("[data-role=maintenance-leave]").attributes("disabled") === undefined).toBe(enabled);
      wrapper.unmount();
    }
  });

  it("takes the pending write's values into the form and locks it (F12)", async () => {
    let current = inMaintenance();
    const { api } = service(() => current);
    const store = createMaintenanceStore(api);
    const wrapper = mount(MaintenancePage, { props: { store } });
    await flushPromises();
    await wrapper.find("input[name=maintenance-new-slave]").setValue(3); // typed, not yet written
    expect(store.state.form.new.slave_id).toBe(3);
    current = inMaintenance({
      pending: true,
      form_locked: true,
      form_enabled: false,
      write_enabled: false,
      verify_enabled: true,
      form: { serial_port: "COM9", old: { slave_id: 1, baudrate: 19200, parity: "N" }, new: { slave_id: 7, baudrate: 9600, parity: "N" } },
    });
    await store.load();
    await flushPromises();
    expect(store.state.form.serial_port).toBe("COM9");
    expect(store.state.form.new).toEqual({ slave_id: 7, baudrate: 9600, parity: "N" });
    for (const name of ["maintenance-port", "maintenance-new-slave", "maintenance-new-baudrate", "maintenance-old-slave"]) {
      expect(wrapper.find(`[name=${name}]`).attributes("disabled"), name).toBeDefined();
    }
  });

  it("reads the view again after task_finished and the other maintenance events (F7)", async () => {
    const { api, calls } = service(() => view());
    const store = createMaintenanceStore(api);
    const reads = () => calls.filter((call) => call.method === "GET" && call.path === "/maintenance/state").length;
    for (const name of ["task_finished", "maintenance_state", "maintenance_changed", "acquisition_halted", "tier_changed"]) {
      const before = reads();
      store.onEvent({ id: 1, name, data: {} });
      await flushPromises();
      expect(reads(), name).toBe(before + 1);
    }
    const before = reads();
    store.onEvent({ id: 2, name: "sample", data: {} });
    await flushPromises();
    expect(reads()).toBe(before);
  });
});

describe("settings page current values (PR #55 review M1)", () => {
  it("tells the service when the settings page is left, so its automatic re-read stops", async () => {
    const { api, calls } = service(() => view());
    const store = createMaintenanceStore(api);
    const takeover = { listen: () => () => undefined } as unknown as TakeoverStore;
    const wrapper = mount(SettingsMaintenance, { props: { store, takeover } });
    await flushPromises();
    expect(calls.filter((call) => call.path === "/acquisition/devices/p1/comm/read")).toHaveLength(1);
    wrapper.unmount();
    await flushPromises();
    expect(calls.filter((call) => call.method === "DELETE" && call.path === "/acquisition/devices/comm/read")).toHaveLength(1);
  });

  it("keeps showing the last valid values after a failed read, with the service's note (review M3)", async () => {
    const values = ["1", "19200", "无校验"].map((text) => ({ text, mismatch: false, tooltip: text }));
    const settings = {
      North: {
        key: "North",
        source: "当前值 · North · 读取失败",
        error: true,
        tooltip: "超时",
        stale: true,
        stale_text: "以下为上次成功读取的值，本次未能确认",
        values,
      },
    };
    const { api } = service(() => view({ settings }));
    const store = createMaintenanceStore(api);
    const takeover = { listen: () => () => undefined } as unknown as TakeoverStore;
    const wrapper = mount(SettingsMaintenance, { props: { store, takeover } });
    await flushPromises();
    expect(wrapper.find("[data-role=settings-comm-values]").text()).toContain("19200");
    expect(wrapper.find("[data-role=settings-comm-stale]").text()).toBe("以下为上次成功读取的值，本次未能确认");
    wrapper.unmount();
  });
});

describe("tier gating and tokens", () => {
  it("offers the 设备维护 tab only in tier 2", () => {
    const one = mount(PageNav, { props: { view: "settings", tier: 1 } });
    expect(one.text()).not.toContain("设备维护");
    const two = mount(PageNav, { props: { view: "settings", tier: 2 } });
    expect(two.findAll("button").at(-1)?.text()).toBe("设备维护");
  });

  it("uses the direction A maintenance colour with AA contrast", () => {
    const css = readFileSync(join(__dirname, "..", "src", "styles", "tokens.css"), "utf-8");
    expect(css).toMatch(/--color-maintenance:\s*#7c3aed;/);
    expect(css).toMatch(/--color-on-maintenance-container:\s*#5b21b6;/);
  });
});
