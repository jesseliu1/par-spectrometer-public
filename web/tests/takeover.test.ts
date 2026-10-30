/**
 * Tier 1 "接管采集" pages (16_ 7.7; D-214): the event-stream parser and reconnection, the tier and takeover store
 * (two-layer confirmation, stop / 1 → 0 confirmation, events as hints, errors keep the last data), the status bar's
 * five states with their colour tokens, the configuration editor rendering the service's V1.0.3 form, and the
 * overview switching between the snapshot (tier 0, unchanged) and the live takeover view (tier 1).
 */
import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "../src/api/client";
import type {
  AcquisitionConfig,
  AcquisitionStatus,
  ImportPreview,
  LiveOverview,
  SerialPorts,
  Takeover,
  TierConfirmation,
  TierLevel,
  TierState,
} from "../src/api/types";
import AcquisitionConfigEditor from "../src/components/AcquisitionConfigEditor.vue";
import LivePanel from "../src/components/LivePanel.vue";
import StatusLine from "../src/components/StatusLine.vue";
import TierDialog from "../src/components/TierDialog.vue";
import TierPanel from "../src/components/TierPanel.vue";
import { connectEvents, SseParser, type StreamState } from "../src/lib/sse";
import PageNav from "../src/components/PageNav.vue";
import OverviewPage from "../src/pages/OverviewPage.vue";
import { createOverviewStore } from "../src/pages/overviewStore";
import TakeoverDialogs from "../src/components/TakeoverDialogs.vue";
import { createTakeoverStore } from "../src/pages/takeoverStore";
import App from "../src/App.vue";
import { createCalcStore } from "../src/pages/calcStore";
import { createDliStore } from "../src/pages/dliStore";
import { createHistoryStore } from "../src/pages/historyStore";
import { createSettingsStore } from "../src/pages/settingsStore";
import type { ServiceFault } from "../src/api/types";
import { AS_OF, detail, devices, dliDay, health, overview, page, snapshots } from "./fixtures";

vi.mock("echarts/core", () => ({
  use: () => undefined,
  init: () => ({ setOption: () => undefined, resize: () => undefined, dispose: () => undefined }),
}));

const TEXTS: Record<string, [string, TierLevel]> = {
  tier0: ["只读模式（不连接设备）", "muted"],
  released: ["采集模式 · 未在采集（可点“开始采集”）", "info"],
  running: ["采集模式 · 正在采集", "warn"],
  stopping: ["采集模式 · 正在停止采集…", "warn"],
  halted: ["采集模式 · 采集已停止（锁停），见提示", "error"],
};

function tierState(tier: number, takeover: Takeover = "released", which?: string): TierState {
  const [text, level] = TEXTS[which ?? (tier === 0 ? "tier0" : takeover)] ?? TEXTS.released!;
  return {
    tier,
    takeover,
    lock_held: takeover === "running",
    text,
    level,
    settings_path: "/alpha/config/app_config_v2.json",
    settings_problem: null,
    stop_text: STOP_FROM_SERVICE,
    down_text: DOWN_FROM_SERVICE,
    down_to_1_text: "服务给出的切回档位 1 确认",
    maintenance: false,
    fault: null,
  };
}

const STOP_FROM_SERVICE = "服务给出的停止确认（最长约 40 秒）";
const DOWN_FROM_SERVICE = "服务给出的切回档位 0 确认";

function confirmation(): TierConfirmation {
  return {
    confirmation_id: "abc",
    tier: 1,
    expires_at: "2026-10-18T09:31:15.123",
    notice: "开启采集模式之后：\n· 接管期间 V1.0.3 无法启动；",
    confirmation: "我已了解上述影响，开启采集模式。",
  };
}

function status(takeover: Takeover = "running", halt = false): AcquisitionStatus {
  return {
    as_of: AS_OF,
    takeover,
    lock_held: takeover === "running",
    error: null,
    bus: { level: "ok", message: "总线已连接" },
    halt: halt
      ? {
          name: "North",
          slave_id: 1,
          occurred_at: "2026-10-18 09:00:00",
          reason: "需要重新上电",
          text: "锁停全文\n请为该设备重新上电",
          notice: { event_id: "3f9a1c2b-000042", occurred_at: "2026-10-18T09:00:00.000" },
        }
      : null,
    maintenance: false,
    poll_cycle_seconds: 40,
    config_apply_error: null,
    devices: [
      {
        key: "North",
        position: "p1",
        name: "North",
        slave_id: 1,
        enabled: true,
        online: true,
        level: "ok",
        message: "",
        failures: 0,
        excluded: false,
        last_failure_at: null,
        last_success_at: AS_OF,
        last_error: null,
        latest_record_id: 3,
        database_path: "/alpha/data/devices/North.sqlite3",
        status_text: "North（地址 1）· 采集成功",
      },
    ],
    run_status: {
      bus: { text: "总线：已连接", level: "ok", detail: "总线已连接" },
      acquisition: { text: "正常采集", level: "ok" },
      failures: [],
    },
  };
}

function config(): AcquisitionConfig {
  const blank = (slave: number) => ({
    name: "",
    slave_id: slave,
    enabled: false,
    auto_stop_on_failure: false,
    database_path: "",
    database_name: null,
    registered: false,
    reuse_existing: false,
  });
  return {
    as_of: AS_OF,
    path: "/alpha/config/app_config.json",
    exists: true,
    configured: true,
    bus: {
      transport: "rtu",
      serial_port: "COM7",
      host: "",
      tcp_port: 502,
      baudrate: 9600,
      parity: "N",
      timeout_seconds: 1,
      poll_cycle_seconds: 40,
    },
    poll_cycle_seconds: 40,
    devices: [],
    devices_dir: "/alpha/data/devices",
    rows: [
      {
        name: "North",
        slave_id: 1,
        enabled: true,
        auto_stop_on_failure: false,
        database_path: "/alpha/data/devices/North.sqlite3",
        database_name: "North.sqlite3",
        registered: true,
        reuse_existing: false,
      },
      blank(2),
      blank(3),
      blank(4),
    ],
    blank_bus: {
      transport: "rtu",
      serial_port: "",
      host: "",
      tcp_port: 502,
      baudrate: 9600,
      parity: "N",
      timeout_seconds: 1,
      poll_cycle_seconds: 300,
    },
    blank_rows: [blank(1), blank(2), blank(3), blank(4)],
    problem: null,
    form: {
      labels: [
        { key: "transport", label: "连接方式" },
        { key: "serial_port", label: "计算机串口" },
        { key: "baudrate", label: "波特率" },
        { key: "parity", label: "奇偶校验" },
        { key: "host", label: "TCP 主机" },
        { key: "tcp_port", label: "TCP 端口" },
        { key: "poll_cycle_seconds", label: "全总线轮询周期" },
      ],
      transports: [
        { value: "rtu", label: "Modbus RTU（串口）" },
        { value: "tcp", label: "Modbus TCP 客户端（网口）" },
      ],
      baudrates: [4800, 9600],
      parities: [
        { value: "N", label: "无校验" },
        { value: "O", label: "奇校验" },
        { value: "E", label: "偶校验" },
      ],
      parity_tooltip: "8 数据位、1 停止位",
      poll_min: 40,
      poll_max: 3600,
      poll_decimals: 1,
      poll_hint: "下限 40 s；上限 3600 s（60 分钟），不随设备数量变化。",
      poll_tooltip: "轮询周期40至3600秒，与设备数量无关",
      slave_min: 1,
      slave_max: 247,
      tcp_port_min: 1,
      tcp_port_max: 65535,
      device_columns: ["设备名称", "从站地址", "启用采集", "失败停止", "数据库文件"],
      name_placeholders: ["光谱仪1", "光谱仪2", "光谱仪3", "光谱仪4"],
      enabled_tooltip: "勾选后参与总线轮询采集",
      fail_stop_tooltip: "勾选：连续 10 次通信失败后自动退出本次采集",
      save_label: "保存并应用全部配置",
      save_tooltip: "仅保存软件连接参数和设备登记，不写入设备硬件",
      saved_text: "配置已保存，等待当前事务结束后应用。",
      error_title: "配置未应用",
      serial_port_hint: "填写串口名称（如 COM3）",
      new_database_text: "保存时在数据目录新建",
      save_requires_running: "保存会立即应用到正在运行的采集，需先在“实时概览”点“开始采集”。",
      reuse_label: "沿用数据目录中的同名库",
      reuse_tooltip: "只能沿用 alpha 自己数据目录 data/devices 中的库",
      reconfigure_title: "配置或数据库不可用",
      reconfigure_text: "选择重新配置后，原配置暂不修改；明确保存新配置时会先备份原配置。\n\n是否以空配置重新配置？",
      reconfigure_label: "以空配置重新配置…",
      reconfigure_hint: "正在以空配置重新配置：保存时先备份原配置文件，不需要先开始采集。",
      apply_failed_text: "上次保存的配置未生效：正在采集的仍是原配置。可修改后重新保存。",
    },
  };
}

function preview(): ImportPreview {
  const rows = config().rows.map((row, index) =>
    index === 0 ? { ...row, name: "Imported", database_path: "", database_name: null } : row,
  );
  return {
    as_of: AS_OF,
    source_path: "/V1.0.3/config/app_config.json",
    bus: { ...config().bus, serial_port: "COM9" },
    devices: [
      { name: "Imported", slave_id: 1, enabled: true, auto_stop_on_failure: false, source_database_path: "/V1/a", importable: true, problem: null },
      {
        name: "Pending",
        slave_id: 2,
        enabled: true,
        auto_stop_on_failure: false,
        source_database_path: "/V1/b",
        importable: false,
        problem: "该设备在 V1.0.3 中有通信参数写入待核对，请先在 V1.0.3 完成核对，再导入",
      },
    ],
    rows,
    note: "只读取 V1.0.3 的配置文件和设备库，不改动它们。",
  };
}

function serialPorts(count = 2): SerialPorts {
  const all = [
    { value: "COM7", label: "COM7 — USB-SERIAL CH340" },
    { value: "COM3", label: "COM3 — 未知设备" },
  ];
  return {
    as_of: AS_OF,
    ports: all.slice(0, count),
    hint: count > 0 ? `检测到 ${count} 个串口，请手动选择；不会自动搜索或切换端口。` : "未检测到串口；请确认 USB 线、驱动和设备电源。",
  };
}

function live(key = "p1", id = 3): LiveOverview {
  const base = overview(key, id);
  return { ...base, source: "live", device: { key, name: "North", database_path: "/alpha/data/devices/North.sqlite3" }, paused: false };
}

/** A tier-0 service with nothing taken over by default; tier 1 defaults to a running takeover. */
function takeoverApi(tier = 1, takeover: Takeover = tier >= 1 ? "running" : "released") {
  return {
    tier: vi.fn(async () => tierState(tier, takeover)),
    confirmTier: vi.fn(async () => confirmation()),
    setTier: vi.fn(async (next: number) => tierState(next, "released")),
    acquisitionStatus: vi.fn(async () => status(takeover)),
    acquisitionConfig: vi.fn(async () => config()),
    saveAcquisitionConfig: vi.fn(async (_body: unknown) => config()),
    importPreview: vi.fn(async () => preview()),
    serialPorts: vi.fn(async () => serialPorts()),
    startAcquisition: vi.fn(async () => status("running")),
    stopAcquisition: vi.fn(async () => status("stopping")),
    liveOverview: vi.fn(async (key: string) => live(key)),
    openEvents: vi.fn(),
    overview: vi.fn(async (key: string) => overview(key)),
    acquisition: vi.fn(),
  };
}

function takeoverStore(api = takeoverApi()) {
  return { api, store: createTakeoverStore(api as unknown as ApiClient, { connect: false }) };
}

function streamOf(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

describe("SSE parser (API-17)", () => {
  it("joins chunks, skips comments, joins data lines and keeps the id", () => {
    const parser = new SseParser();
    expect(parser.push(": connected\n\nid: 4\nevent: bus_state\nda")).toEqual([]);
    const [first] = parser.push('ta: {"level":"ok",\ndata: "message":"总线已连接"}\n\n');
    expect(first).toEqual({ id: 4, name: "bus_state", data: { level: "ok", message: "总线已连接" } });
  });

  it("accepts CRLF split across chunks and drops a message without data", () => {
    const parser = new SseParser();
    expect(parser.push("event: heartbeat\r")).toEqual([]);
    expect(parser.push("\n\r\nevent: tier_changed\r\ndata: {\"tier\":1}\r\n\r\n")).toEqual([
      { id: null, name: "tier_changed", data: { tier: 1 } },
    ]);
  });
});

describe("event stream connection", () => {
  it("reconnects after the stream ends and reports each (re)connection; close ends the loop", async () => {
    const states: StreamState[] = [];
    const events: string[] = [];
    let opened = 0;
    let stream: ReturnType<typeof connectEvents> | null = null;
    stream = connectEvents({
      open: async () => {
        opened += 1;
        if (opened === 2) throw new ApiError(0, { code: "service_unavailable", message: "x", retryable: true, detail: null });
        return streamOf([`event: acquisition_saved\ndata: {"key":"North","record_id":${opened}}\n\n`]);
      },
      onEvent: (event) => events.push(`${event.name}:${String(event.data.record_id)}`),
      onState: (state) => {
        states.push(state);
        if (opened >= 3 && state === "open") stream?.close();
      },
      sleep: async () => undefined,
    });
    await stream.done;
    expect(opened).toBe(3);
    expect(events).toEqual(["acquisition_saved:1", "acquisition_saved:3"]);
    expect(states).toEqual(["connecting", "open", "reconnecting", "reconnecting", "open", "closed"]);
  });

  it("waits 1 s doubling to 10 s while the service stays away, and starts again at 1 s after a connection", async () => {
    const waits: number[] = [];
    let opened = 0;
    let stream: ReturnType<typeof connectEvents> | null = null;
    stream = connectEvents({
      open: async () => {
        opened += 1;
        if (opened === 7) return streamOf([]); // connected once, then the stream ends
        if (opened === 9) stream?.close();
        throw new ApiError(0, { code: "service_unavailable", message: "x", retryable: true, detail: null });
      },
      onEvent: () => undefined,
      onState: () => undefined,
      sleep: async (ms) => {
        waits.push(ms);
      },
    });
    await stream.done;
    expect(waits).toEqual([1000, 2000, 4000, 8000, 10000, 10000, 1000, 1000]);
  });
});

describe("tier and takeover store (16_ 4, 5)", () => {
  it("reads the tier; the status only in tier 1", async () => {
    const { api, store } = takeoverStore(takeoverApi(0));
    await store.init();
    expect(store.state.tier.data?.text).toBe("只读模式（不连接设备）");
    expect(api.acquisitionStatus).not.toHaveBeenCalled();
  });

  it("0 → 1 needs both layers and the acknowledgement; cancelling writes nothing", async () => {
    const { api, store } = takeoverStore(takeoverApi(0));
    await store.init();
    await store.askTier(1);
    expect(api.confirmTier).toHaveBeenCalledWith(1);
    expect(store.state.dialog).toBe("notice");
    expect(await store.acceptTier()).toBe(false); // still on the first layer
    store.continueTier();
    expect(store.state.dialog).toBe("confirm");
    expect(await store.acceptTier()).toBe(false); // not acknowledged
    expect(api.setTier).not.toHaveBeenCalled();
    store.cancelDialog();
    expect(store.state.dialog).toBe("none");
    expect(api.setTier).not.toHaveBeenCalled();

    await store.askTier(1);
    store.continueTier();
    store.setAcknowledged(true);
    expect(await store.acceptTier()).toBe(true);
    expect(api.setTier).toHaveBeenCalledWith(1, "abc");
    expect(store.state.dialog).toBe("none");
  });

  it("a refused confirmation (expired or used) is shown and not retried with the same id", async () => {
    const api = takeoverApi(0);
    api.setTier.mockRejectedValueOnce(
      new ApiError(409, { code: "confirmation_required", message: "确认已过期，请重新确认", retryable: false, detail: null }),
    );
    const { store } = takeoverStore(api);
    await store.init();
    await store.askTier(1);
    store.continueTier();
    store.setAcknowledged(true);
    expect(await store.acceptTier()).toBe(false);
    expect(store.state.tierChange.error?.message).toBe("确认已过期，请重新确认");
    expect(store.state.tierChange.retry).toBeNull();
    expect(store.state.tier.data?.tier).toBe(0);
  });

  it("1 → 0 and 停止采集 each ask once; 否 changes nothing", async () => {
    const { api, store } = takeoverStore();
    await store.init();
    store.askStop();
    expect(store.state.dialog).toBe("stop");
    store.cancelDialog();
    expect(await store.confirmStop()).toBe(false);
    expect(api.stopAcquisition).not.toHaveBeenCalled();
    store.askStop();
    expect(await store.confirmStop()).toBe(true);
    expect(api.stopAcquisition).toHaveBeenCalledTimes(1);
    await store.askTier(0);
    expect(store.state.dialog).toBe("down");
    expect(await store.confirmDown()).toBe(true);
    expect(api.setTier).toHaveBeenCalledWith(0);
  });

  it("confirmDown sends nothing unless the 切回档位 0 confirmation is open (review T3)", async () => {
    const { api, store } = takeoverStore();
    await store.init();
    expect(await store.confirmDown()).toBe(false);
    store.askStop();
    expect(await store.confirmDown()).toBe(false);
    expect(store.state.dialog).toBe("stop");
    expect(api.setTier).not.toHaveBeenCalled();
  });

  it("tier_changed and takeover_state reload the tier and the status: a 202 stop or lowering ends there (review T2)", async () => {
    const api = takeoverApi(1, "running");
    const { store } = takeoverStore(api);
    await store.init();
    api.stopAcquisition.mockResolvedValueOnce(status("stopping"));
    api.tier.mockResolvedValueOnce(tierState(1, "stopping"));
    store.askStop();
    expect(await store.confirmStop()).toBe(true);
    expect(store.state.tier.data?.text).toBe(TEXTS.stopping![0]);
    api.tier.mockResolvedValue(tierState(1, "released"));
    api.acquisitionStatus.mockResolvedValue(status("released"));
    store.onEvent({ id: 8, name: "takeover_state", data: { state: "released" } });
    await flushPromises();
    expect(store.state.tier.data?.text).toBe(TEXTS.released![0]);
    expect(store.state.status.data?.takeover).toBe("released");
    api.tier.mockResolvedValue(tierState(0, "released"));
    store.onEvent({ id: 9, name: "tier_changed", data: { tier: 0 } });
    await flushPromises();
    expect(store.state.tier.data?.tier).toBe(0);
    expect(store.state.tier.data?.text).toBe(TEXTS.tier0![0]);
    expect(store.state.status.data).toBeNull(); // tier 0: no status any more
  });

  it("config_applied reads the tier and the status again: 等待登记设备 ends once a device is saved", async () => {
    const { api, store } = takeoverStore(takeoverApi(1, "running"));
    await store.init();
    api.tier.mockClear();
    api.acquisitionStatus.mockClear();
    store.onEvent({ id: 7, name: "config_applied", data: { configured: true } });
    await flushPromises();
    expect(api.tier).toHaveBeenCalledTimes(1);
    expect(api.acquisitionStatus).toHaveBeenCalledTimes(1);
  });

  it("the stop and 切回档位 0 confirmations show the service's texts (review nit, Q1)", async () => {
    const api = takeoverApi(1, "running");
    api.tier.mockResolvedValue({ ...tierState(1, "running"), stop_text: "停止确认\n\n锁停全文：请先为设备重新上电" });
    const { store } = takeoverStore(api);
    await store.init();
    store.askStop();
    const dialogs = mount(TakeoverDialogs, { props: { store } });
    expect(dialogs.text()).toContain("锁停全文：请先为设备重新上电");
    await store.askTier(0);
    await flushPromises();
    expect(dialogs.text()).toContain(DOWN_FROM_SERVICE);
  });

  it("events are hints: the state is read again; saved records are counted; a reconnection reloads the tier", async () => {
    const { api, store } = takeoverStore();
    await store.init();
    api.acquisitionStatus.mockClear();
    store.onEvent({ id: 5, name: "device_state", data: { key: "North" } });
    await flushPromises();
    expect(api.acquisitionStatus).toHaveBeenCalledTimes(1);
    store.onEvent({ id: 6, name: "acquisition_saved", data: { key: "North", record_id: 9 } });
    expect(store.state.savedRecords).toBe(1);
    expect(store.state.lastSaved).toEqual({ key: "North", record_id: 9 });
    api.tier.mockClear();
    store.onStream("open");
    await flushPromises();
    expect(api.tier).toHaveBeenCalledTimes(1);
    store.onStream("reconnecting");
    expect(store.state.stream).toBe("reconnecting");
  });

  it("a failed status read keeps the last status (R-1-5)", async () => {
    const api = takeoverApi();
    const { store } = takeoverStore(api);
    await store.init();
    api.acquisitionStatus.mockRejectedValueOnce(
      new ApiError(0, { code: "service_unavailable", message: "无法连接本机服务", retryable: true, detail: null }),
    );
    expect(await store.loadStatus()).toBe(false);
    expect(store.state.status.error?.code).toBe("service_unavailable");
    expect(store.state.status.data?.bus.message).toBe("总线已连接");
  });

  it("start refused by V1.0.3's lock shows the service's message", async () => {
    const api = takeoverApi(1, "released");
    api.startAcquisition.mockRejectedValueOnce(
      new ApiError(409, {
        code: "instance_locked",
        message: "V1.0.3 正在运行（或另一个程序正在使用串口），本次未开始采集。请先退出 V1.0.3。",
        retryable: true,
        detail: null,
      }),
    );
    const { store } = takeoverStore(api);
    await store.init();
    expect(await store.start()).toBe(false);
    expect(store.state.action.error?.message).toContain("请先退出 V1.0.3");
  });

  it("a start refused by a click also names its record (issue 136, PR 143 review)", async () => {
    const message = "V1.0.3 正在运行（或另一个程序正在使用串口），本次未开始采集。请先退出 V1.0.3。";
    const api = takeoverApi(1, "released");
    api.startAcquisition.mockRejectedValueOnce(
      new ApiError(409, { code: "instance_locked", message, retryable: true, detail: null }),
    );
    api.acquisitionStatus.mockResolvedValue({
      ...status("released"),
      error: message,
      error_notice: { event_id: "0123456789abcdef-000003", occurred_at: "2026-10-28T16:00:00.000" },
    });
    const { store } = takeoverStore(api);
    await store.init();
    const panel = mount(LivePanel, { props: { store, devices: [], selected: null } });
    expect(await store.start()).toBe(false);
    await flushPromises();
    expect(panel.get("[data-role=action-notice]").text()).toBe(
      "记录号 0123456789abcdef-000003，出现于 2026-10-28 16:00:00.000",
    );
    expect(panel.find("[data-role=start-refused]").exists()).toBe(false); // the click's error shows it once
  });

  it("the halt banner closes with 确认 and comes back for a new halt; nothing clears the halt", async () => {
    const api = takeoverApi();
    api.acquisitionStatus.mockResolvedValue(status("running", true));
    const { store } = takeoverStore(api);
    await store.init();
    expect(store.haltVisible()).toBe(true);
    store.dismissHalt();
    expect(store.haltVisible()).toBe(false);
    expect(Object.keys(store)).not.toContain("clearHalt");
  });

  it("saving sends the four rows; a refusal keeps the form as typed, a success shows V1.0.3's saved text", async () => {
    const api = takeoverApi();
    api.saveAcquisitionConfig.mockRejectedValueOnce(
      new ApiError(400, { code: "invalid_argument", message: "设备 ID 必须在 1~247 之间，且不能重复。", retryable: false, detail: null }),
    );
    const { store } = takeoverStore(api);
    await store.init();
    await store.loadConfig();
    store.setRow(1, "name", "South");
    store.setRow(1, "slave_id", 1);
    expect(await store.save()).toBe(false);
    expect(store.state.saving.error?.message).toBe("设备 ID 必须在 1~247 之间，且不能重复。");
    expect(store.state.draft?.rows[1]?.name).toBe("South");
    expect(store.state.dirty).toBe(true);
    const calls = api.saveAcquisitionConfig.mock.calls as unknown as [{ devices: unknown[] }][];
    const body = calls[0]![0];
    expect(body.devices).toHaveLength(4);
    expect(body.devices[1]).toEqual({
      name: "South",
      slave_id: 1,
      enabled: false,
      auto_stop_on_failure: false,
      database_path: "",
      reuse_existing: false,
    });
    store.setRow(1, "slave_id", 2);
    expect(await store.save()).toBe(true);
    expect(store.state.saved).toBe(true);
    expect(store.state.dirty).toBe(false);
  });

  it("an import preview goes into the form only on 放入表单 and is not saved by itself", async () => {
    const { api, store } = takeoverStore();
    await store.init();
    await store.loadConfig();
    store.setImportPath("/V1.0.3");
    expect(await store.previewImport()).toBe(true);
    expect(api.importPreview).toHaveBeenCalledWith("/V1.0.3");
    expect(store.state.draft?.rows[0]?.name).toBe("North");
    expect(store.applyImport()).toBe(true);
    expect(store.state.draft?.rows[0]?.name).toBe("Imported");
    expect(store.state.draft?.bus.serial_port).toBe("COM9");
    expect(store.state.dirty).toBe(true);
    expect(api.saveAcquisitionConfig).not.toHaveBeenCalled();
  });
});

const TAKEOVER_FAULT_TEXT = "采集或设备维护时出现内部错误（已记入 service.log）……并切回档位 0。";

function fault(id: number, kind: ServiceFault["kind"] = "takeover"): ServiceFault {
  return {
    id,
    kind,
    occurred_at: "2026-10-19T10:00:00.000",
    where: kind === "takeover" ? "a Qt slot or callback" : "GET /api/v0/devices/p1/acquisitions",
    error: "RuntimeError",
    message: kind === "takeover" ? TAKEOVER_FAULT_TEXT : "本机服务处理请求时出现内部错误……可点“重试”。",
    stopping: kind === "takeover",
  };
}

describe("an unexpected service error (D-225 item 1, R-1-5)", () => {
  it("service_error reads the tier again: the takeover is released at tier 0 and the fault shows until 知道了", async () => {
    const api = takeoverApi(1, "running");
    const { store } = takeoverStore(api);
    await store.init();
    expect(store.faultShown()).toBeNull();
    api.tier.mockResolvedValue({ ...tierState(0, "released"), fault: fault(1) });
    store.onEvent({ id: 12, name: "service_error", data: { id: 1, kind: "takeover" } });
    await flushPromises();
    expect(store.state.tier.data?.tier).toBe(0);
    expect(store.state.status.data).toBeNull(); // tier 0, released: no status read any more
    expect(store.faultShown()?.message).toBe(TAKEOVER_FAULT_TEXT);
    store.dismissFault();
    expect(store.faultShown()).toBeNull();
    api.tier.mockResolvedValue({ ...tierState(0, "released"), fault: fault(2, "request") });
    await store.loadTier();
    expect(store.faultShown()?.kind).toBe("request"); // a newer fault shows again
  });

  it("a failed request keeps the last data and offers a retry; the banner is the service's text", async () => {
    const api = {
      ...takeoverApi(1, "running"),
      health: vi.fn(async () => health()),
      snapshots: vi.fn(async () => snapshots()),
      devices: vi.fn(async () => devices(["p1"])),
      acquisitions: vi.fn(async () => page([])),
      acquisition: vi.fn(async (key: string, id: number) => detail(id, key)),
      importSnapshot: vi.fn(),
    };
    const client = api as unknown as ApiClient;
    const takeover = createTakeoverStore(client, { connect: false });
    const wrapper = mount(App, {
      props: {
        store: createHistoryStore(client),
        dli: createDliStore(client),
        calc: createCalcStore(client),
        settings: createSettingsStore(client),
        overview: createOverviewStore(client),
        takeover,
        initialView: "overview",
      },
      global: { stubs: { SpectrumChart: true, OverviewChart: true } },
    });
    await flushPromises();
    expect(wrapper.find("[data-role=service-fault]").exists()).toBe(false);
    const shown = takeover.state.status.data;
    api.acquisitionStatus.mockRejectedValueOnce(
      new ApiError(500, { code: "internal", message: "服务内部错误，请重试", retryable: true, detail: "RuntimeError" }),
    );
    api.tier.mockResolvedValue({ ...tierState(1, "running"), fault: fault(1, "request") });
    takeover.onEvent({ id: 3, name: "service_error", data: { id: 1, kind: "request" } });
    await flushPromises();
    expect(takeover.state.status.data).toEqual(shown); // the last valid status stays
    expect(takeover.state.status.error?.code).toBe("internal");
    expect(await takeover.state.status.retry?.()).toBe(true);
    const banner = wrapper.get("[data-role=service-fault]");
    expect(banner.attributes("role")).toBe("alert");
    expect(banner.text()).toContain("可点“重试”");
    await banner.get("button").trigger("click");
    expect(wrapper.find("[data-role=service-fault]").exists()).toBe(false);
    wrapper.unmount();
  });
});

describe("device list follows the tier and the configuration (issue #82)", () => {
  it("the DLI page reads again when the viewed position got another database (PR #95 review)", async () => {
    const api = {
      ...takeoverApi(1, "released"),
      health: vi.fn(async () => health()),
      devices: vi.fn(async () => devices(["p1"])),
      acquisitions: vi.fn(async () => page([])),
      acquisition: vi.fn(async (key: string, id: number) => detail(id, key)),
      dli: vi.fn(async (key: string) => dliDay(key)),
    };
    const client = api as unknown as ApiClient;
    const takeover = createTakeoverStore(client, { connect: false });
    const wrapper = mount(App, {
      props: {
        store: createHistoryStore(client),
        dli: createDliStore(client),
        calc: createCalcStore(client),
        settings: createSettingsStore(client),
        overview: createOverviewStore(client),
        takeover,
        initialView: "dli",
      },
      global: { stubs: { SpectrumChart: true, OverviewChart: true, DliChart: true } },
    });
    await flushPromises();
    const reads = api.dli.mock.calls.length;
    expect(reads).toBeGreaterThan(0);
    api.devices.mockResolvedValue(devices(["p1"], { p1: "p1-another" }));
    takeover.onEvent({ id: 1, name: "config_applied", data: {} });
    await flushPromises();
    expect(api.dli.mock.calls.length).toBeGreaterThan(reads);
    expect(api.dli).toHaveBeenLastCalledWith("p1", null);
    wrapper.unmount();
  });

  it("reads the devices again on a tier change and when a saved configuration is applied", async () => {
    const api = {
      ...takeoverApi(0, "released"),
      health: vi.fn(async () => health()),
      devices: vi.fn(async () => devices([])),
      acquisitions: vi.fn(async () => page([])),
      acquisition: vi.fn(async (key: string, id: number) => detail(id, key)),
    };
    const client = api as unknown as ApiClient;
    const takeover = createTakeoverStore(client, { connect: false });
    const store = createHistoryStore(client);
    const wrapper = mount(App, {
      props: {
        store,
        dli: createDliStore(client),
        calc: createCalcStore(client),
        settings: createSettingsStore(client),
        overview: createOverviewStore(client),
        takeover,
      },
      global: { stubs: { SpectrumChart: true, OverviewChart: true } },
    });
    await flushPromises();
    expect(store.state.deviceKey).toBeNull();
    expect(wrapper.get("[data-role=no-device]").text()).toContain("开启采集模式");

    api.tier.mockResolvedValue(tierState(1, "released"));
    api.devices.mockResolvedValue(devices(["p1"]));
    takeover.onEvent({ id: 1, name: "tier_changed", data: { tier: 1 } });
    await flushPromises();
    expect(store.state.deviceKey).toBe("p1");
    expect(api.acquisitions).toHaveBeenCalledWith("p1", expect.anything());

    api.devices.mockResolvedValue(devices(["p1", "p2"]));
    const reads = api.devices.mock.calls.length;
    takeover.onEvent({ id: 2, name: "config_applied", data: {} });
    await flushPromises();
    expect(api.devices.mock.calls.length).toBe(reads + 1);
    expect(store.state.devices.data?.items[1]?.configured).toBe(true);
    expect(store.state.deviceKey).toBe("p1");

    // a configuration applied while the event stream was down: the reconnection reads the list again (PR #95)
    api.devices.mockResolvedValue(devices(["p1", "p2", "p3"]));
    takeover.state.stream = "open";
    await flushPromises();
    takeover.state.stream = "reconnecting";
    await flushPromises();
    takeover.state.stream = "open";
    await flushPromises();
    expect(store.state.devices.data?.items[2]?.configured).toBe(true);

    api.tier.mockResolvedValue(tierState(0, "released"));
    api.devices.mockResolvedValue(devices([]));
    takeover.onEvent({ id: 3, name: "tier_changed", data: { tier: 0 } });
    await flushPromises();
    expect(store.state.deviceKey).toBeNull();
    expect(wrapper.find("[data-role=no-device]").exists()).toBe(true);
    wrapper.unmount();
  });
});

describe("tier components", () => {
  it("the status bar shows the service's tier text with its colour token (16_ 4.4)", () => {
    for (const [, [text, level]] of Object.entries(TEXTS)) {
      const state = { ...tierState(1), text, level };
      const wrapper = mount(StatusLine, { props: { asOf: null, sourceText: null, tier: 1, tierState: state } });
      const block = wrapper.get("[data-role=tier-text]");
      expect(block.text()).toBe(text);
      expect(block.classes()).toContain(level);
      expect(wrapper.text()).not.toContain("只读模式 · 不连接设备"); // the tier-0 fallback is not shown beside it
    }
  });

  it("the tier dialog has two layers; 开启档位 1 waits for the checkbox", async () => {
    const notice = mount(TierDialog, { props: { step: "notice", confirmation: confirmation(), acknowledged: false } });
    expect(notice.get("[data-role=tier-notice]").text()).toContain("接管期间 V1.0.3 无法启动");
    await notice.get("[data-role=tier-next]").trigger("click");
    expect(notice.emitted("next")).toHaveLength(1);
    const second = mount(TierDialog, { props: { step: "confirm", confirmation: confirmation(), acknowledged: false } });
    expect(second.get("[data-role=tier-accept]").attributes("disabled")).toBeDefined();
    await second.get("input[type=checkbox]").setValue(true);
    expect(second.emitted("acknowledge")?.[0]).toEqual([true]);
    await second.setProps({ acknowledged: true });
    expect(second.get("[data-role=tier-accept]").attributes("disabled")).toBeUndefined();
  });

  it("the panel offers only the maintenance switch in tier 1; 开启采集 only if the settings still say tier 0 (issue 119)", async () => {
    const zero = takeoverStore(takeoverApi(0));
    await zero.store.init();
    const panel = mount(TierPanel, { props: { store: zero.store } });
    expect(panel.find("[data-role=tier-up]").exists()).toBe(true);
    expect(panel.get(".panel-title").text()).toBe("设备维护模式");
    expect(panel.text()).toContain("本软件打开后自动开始采集");
    expect(panel.text()).not.toContain("内部试用");
    await panel.get("[data-role=tier-up]").trigger("click");
    await flushPromises();
    expect(zero.store.state.dialog).toBe("notice");
    const one = takeoverStore(takeoverApi(1));
    await one.store.init();
    const second = mount(TierPanel, { props: { store: one.store } });
    expect(second.find("[data-role=tier-down]").exists()).toBe(false); // no way back to read-only on the page
    expect(second.find("[data-role=tier-up]").exists()).toBe(false);
    expect(second.get("[data-role=tier-up-2]").text()).toBe("开启维护模式…");
    expect(second.text()).not.toContain("只读模式");
  });

  it("the live panel: start only when released, stop only when running, the halt banner has no clear control", async () => {
    const { api, store } = takeoverStore(takeoverApi(1, "running"));
    api.acquisitionStatus.mockResolvedValue(status("running", true));
    await store.init();
    const panel = mount(LivePanel, {
      props: { store, devices: [{ key: "p1", name: "North", text: "North（地址 1）· 采集成功", level: "ok" }], selected: "p1" },
    });
    expect(panel.get("[data-role=start]").attributes("disabled")).toBeDefined();
    expect(panel.get("[data-role=stop]").attributes("disabled")).toBeUndefined();
    expect(panel.get("[data-key=p1] .position").text()).toBe("1"); // alpha.5: the position number, no "p"
    expect(panel.get("[data-role=bus-state]").text()).toBe("总线已连接") // no doubled "总线：" (#128);
    expect(panel.get("[data-role=halt]").text()).toContain("请为该设备重新上电");
    // issue 136: the banner names the record to look up in the diagnostics bundle
    expect(panel.get("[data-role=halt-notice]").text()).toBe("记录号 3f9a1c2b-000042，出现于 2026-10-18 09:00:00.000");
    expect(panel.findAll("button").map((button) => button.text())).not.toContain("清除锁停");
    await panel.get("[data-role=stop]").trigger("click");
    expect(store.state.dialog).toBe("stop");
    await panel.get("[data-role=halt-ok]").trigger("click");
    expect(panel.find("[data-role=halt]").exists()).toBe(false);
  });

  it("the live panel's bus line reads 总线：异常 like the top bar when no enabled device answers (issue 131)", async () => {
    const { api, store } = takeoverStore(takeoverApi(1, "running"));
    const base = status("running");
    const bus = { text: "总线：异常", level: "error" as const, detail: "所有启用的设备都不响应，将继续按周期重试", devices_silent: true };
    api.acquisitionStatus.mockResolvedValue({ ...base, run_status: { ...base.run_status, bus } });
    await store.init();
    const panel = mount(LivePanel, { props: { store, devices: [], selected: null } });
    const line = panel.get("[data-role=bus-state]");
    expect(line.text()).toBe("总线：异常（所有启用的设备都不响应，将继续按周期重试）");
    expect(line.classes()).toContain("error");
  });

  it("the live panel says when run events did not reach the log file (issue 136)", async () => {
    const { api, store } = takeoverStore(takeoverApi(1, "running"));
    const health = { session: "3f9a1c2b", written: 10, last_written_sequence: 10, dropped: 2, failed: 1 };
    api.acquisitionStatus.mockResolvedValue({
      ...status("running"),
      event_log: { ...health, first_error: "PermissionError: 只读", last_error: "PermissionError: 只读" },
    });
    await store.init();
    const panel = mount(LivePanel, { props: { store, devices: [], selected: null } });
    expect(panel.get("[data-role=event-log-problem]").text()).toBe(
      "运行日志有记录未写入文件：2 条因写盘排满未写入；1 条写盘失败（PermissionError: 只读）。当前提示的记录号仍在，导出诊断包时会补上。",
    );
  });

  it("the live panel shows why the automatic start was refused until a start of the page reports instead (#92)", async () => {
    const locked = "V1.0.3 正在运行（或另一个程序正在使用串口），本次未开始采集。请先退出 V1.0.3。";
    const api = takeoverApi(1, "released");
    api.acquisitionStatus.mockResolvedValue({ ...status("released"), error: locked });
    const { store } = takeoverStore(api);
    await store.init();
    const panel = mount(LivePanel, { props: { store, devices: [], selected: null } });
    expect(panel.get("[data-role=start-refused]").text()).toBe(`未能开始采集：${locked}`);
    expect(panel.get("[data-role=start]").attributes("disabled")).toBeUndefined();
    api.startAcquisition.mockRejectedValueOnce(
      new ApiError(409, { code: "instance_locked", message: locked, retryable: true, detail: null }),
    );
    await panel.get("[data-role=start]").trigger("click");
    await flushPromises();
    expect(panel.find("[data-role=start-refused]").exists()).toBe(false); // the request's own notice shows it once
  });

  it("a new row may reuse the same-name database of the alpha folder; registered rows do not offer it (D-215)", async () => {
    const { api, store } = takeoverStore();
    await store.init();
    await store.loadConfig();
    const editor = mount(AcquisitionConfigEditor, { props: { store } });
    expect(editor.find("input[name=device-reuse-0]").exists()).toBe(false);
    const reuse = editor.get("input[name=device-reuse-2]");
    expect(reuse.element.closest("label")?.textContent).toContain("沿用数据目录中的同名库");
    await editor.get("input[name=device-name-2]").setValue("West");
    await reuse.setValue(true);
    await editor.get("[data-role=config-save]").trigger("click");
    await flushPromises();
    const calls = api.saveAcquisitionConfig.mock.calls as unknown as [{ devices: { reuse_existing: boolean }[] }][];
    expect(calls[0]![0].devices.map((row) => row.reuse_existing)).toEqual([false, false, true, false]);
  });

  it("the configuration editor renders the service's form and shows a refusal with V1.0.3's text", async () => {
    const api = takeoverApi();
    api.saveAcquisitionConfig.mockRejectedValueOnce(
      new ApiError(400, { code: "invalid_argument", message: "请选择串口。", retryable: false, detail: null }),
    );
    const { store } = takeoverStore(api);
    await store.init();
    await store.loadConfig();
    const editor = mount(AcquisitionConfigEditor, { props: { store } });
    expect(editor.text()).toContain("全总线轮询周期");
    expect(editor.find("[data-role=import]").exists()).toBe(false); // issue 119: 从 V1.0.3 配置导入副本 not shown
    expect(editor.text()).not.toContain("V1.0.3");
    expect(editor.text()).toContain("下限 40 s；上限 3600 s（60 分钟），不随设备数量变化。");
    expect(editor.findAll("[data-role=devices] tbody tr")).toHaveLength(4);
    expect(editor.get("input[name=device-name-1]").attributes("placeholder")).toBe("光谱仪2");
    expect(editor.get("input[name=bus-poll-cycle]").attributes("min")).toBe("40");
    await editor.get("input[name=bus-serial-port]").setValue("");
    await editor.get("[data-role=config-save]").trigger("click");
    await flushPromises();
    expect(editor.get("[data-role=config-error]").text()).toContain("配置未应用");
    expect(editor.get("[data-role=config-error]").text()).toContain("请选择串口。");
    expect((editor.get("input[name=bus-serial-port]").element as HTMLInputElement).value).toBe("");
  });
});

describe("计算机串口 list and 刷新串口 (#74, V1.0.3 refresh_serial_ports)", () => {
  it("lists the service's ports when the RTU fields show; picking one fills the name, typing stays free", async () => {
    const { api, store } = takeoverStore();
    await store.init();
    await store.loadConfig();
    const editor = mount(AcquisitionConfigEditor, { props: { store } });
    await flushPromises();
    expect(api.serialPorts).toHaveBeenCalledTimes(1);
    const field = editor.get("input[name=bus-serial-port]");
    expect(field.attributes("title")).toBe("检测到 2 个串口，请手动选择；不会自动搜索或切换端口。");
    expect(editor.find("[data-role=serial-ports]").exists()).toBe(false);
    await editor.get("[data-role=serial-ports-toggle]").trigger("click");
    const options = editor.findAll("[data-role=serial-ports] [role=option]");
    expect(options.map((option) => option.text())).toEqual(["COM7 — USB-SERIAL CH340", "COM3 — 未知设备"]);
    expect(options[0]!.attributes("aria-selected")).toBe("true"); // the configured COM7
    await options[1]!.trigger("click");
    expect(store.state.draft?.bus.serial_port).toBe("COM3");
    expect((field.element as HTMLInputElement).value).toBe("COM3");
    expect(editor.find("[data-role=serial-ports]").exists()).toBe(false);
    await field.setValue("COM12");
    expect(store.state.draft?.bus.serial_port).toBe("COM12");
    expect(store.state.dirty).toBe(true);
  });

  it("the list works from the keyboard: arrows move from the current port, Enter takes it, Esc closes", async () => {
    const { store } = takeoverStore();
    await store.init();
    await store.loadConfig();
    const editor = mount(AcquisitionConfigEditor, { props: { store } });
    await flushPromises();
    const field = editor.get("input[name=bus-serial-port]");
    await field.trigger("keydown", { key: "ArrowDown" });
    expect(field.attributes("aria-activedescendant")).toBe("serial-port-0"); // opens on the configured COM7
    await field.trigger("keydown", { key: "ArrowDown" });
    expect(field.attributes("aria-activedescendant")).toBe("serial-port-1");
    expect(editor.get("#serial-port-1").classes()).toContain("active");
    await field.trigger("keydown", { key: "ArrowDown" });
    expect(field.attributes("aria-activedescendant")).toBe("serial-port-0"); // wraps round
    await field.trigger("keydown", { key: "ArrowUp" });
    await field.trigger("keydown", { key: "Enter" });
    expect(store.state.draft?.bus.serial_port).toBe("COM3");
    expect(editor.find("[data-role=serial-ports]").exists()).toBe(false);
    await field.trigger("keydown", { key: "ArrowDown" });
    expect(field.attributes("aria-activedescendant")).toBe("serial-port-1");
    await field.trigger("keydown", { key: "Escape" });
    expect(editor.find("[data-role=serial-ports]").exists()).toBe(false);
    await field.trigger("keydown", { key: "Enter" });
    expect(store.state.draft?.bus.serial_port).toBe("COM3"); // Enter with the list closed picks nothing
  });

  it("刷新串口 reads the list again; a failure keeps the last list and offers a retry (R-1-5)", async () => {
    const api = takeoverApi();
    const { store } = takeoverStore(api);
    await store.init();
    await store.loadConfig();
    const editor = mount(AcquisitionConfigEditor, { props: { store } });
    await flushPromises();
    api.serialPorts.mockRejectedValueOnce(
      new ApiError(500, { code: "internal", message: "串口枚举失败：access denied", retryable: true, detail: null }),
    );
    const refresh = editor.get("[data-role=serial-refresh]");
    expect(refresh.text()).toBe("刷新串口");
    await refresh.trigger("click");
    await flushPromises();
    expect(api.serialPorts).toHaveBeenCalledTimes(2);
    const notice = editor.get("[data-role=serial-ports-error]");
    expect(notice.text()).toContain("串口枚举失败：access denied");
    expect(notice.text()).toContain("仍显示上次读取的串口列表");
    await editor.get("[data-role=serial-ports-toggle]").trigger("click");
    expect(editor.findAll("[data-role=serial-ports] [role=option]")).toHaveLength(2);
    api.serialPorts.mockResolvedValueOnce(serialPorts(0));
    await notice.get("button").trigger("click");
    await flushPromises();
    expect(api.serialPorts).toHaveBeenCalledTimes(3);
    expect(editor.find("[data-role=serial-ports-error]").exists()).toBe(false);
    expect(editor.findAll("[data-role=serial-ports] [role=option]")).toHaveLength(0);
    expect(editor.get("[data-role=serial-ports-empty]").text()).toBe("未检测到串口；请确认 USB 线、驱动和设备电源。");
  });

  it("TCP shows no port list and asks for none; switching to RTU reads it", async () => {
    const api = takeoverApi();
    api.acquisitionConfig.mockResolvedValue({ ...config(), bus: { ...config().bus, transport: "tcp" } });
    const { store } = takeoverStore(api);
    await store.init();
    await store.loadConfig();
    const editor = mount(AcquisitionConfigEditor, { props: { store } });
    await flushPromises();
    expect(api.serialPorts).not.toHaveBeenCalled();
    expect(editor.find("[data-role=serial-refresh]").exists()).toBe(false);
    await editor.get("select[name=bus-transport]").setValue("rtu");
    await flushPromises();
    expect(api.serialPorts).toHaveBeenCalledTimes(1);
    expect(editor.find("[data-role=serial-refresh]").exists()).toBe(true);
  });
});

describe("overview in tier 1 (live) and tier 0 (snapshot)", () => {
  it("the 实时概览 tab carries no 快照 tag in either tier (issue #82)", () => {
    const zero = mount(PageNav, { props: { view: "overview", live: false } });
    expect(zero.find("[data-view=overview] [data-role=snapshot-tag]").exists()).toBe(false);
    const one = mount(PageNav, { props: { view: "overview", live: true } });
    expect(one.find("[data-view=overview] [data-role=snapshot-tag]").exists()).toBe(false);
    expect(one.get("[data-view=overview]").text()).toBe("实时概览");
  });

  it("tier 1 shows the takeover and the live record of the alpha's own database", async () => {
    const api = takeoverApi(1, "running");
    const { store } = takeoverStore(api);
    await store.init();
    const overviewStore = createOverviewStore(api as unknown as ApiClient);
    const page = mount(OverviewPage, { props: { store: overviewStore, takeover: store } });
    await flushPromises();
    expect(page.find("[data-role=snapshot]").exists()).toBe(false);
    expect(page.get("[data-role=live-banner]").text()).toBe("实时数据");
    expect(api.liveOverview).toHaveBeenCalledWith("p1");
    expect(page.get("[data-role=status]").text()).toContain("显示 #3");
    expect(page.get("[data-role=details-button]").attributes("disabled")).toBeUndefined(); // issue #106
    api.liveOverview.mockClear();
    store.onEvent({ id: 7, name: "acquisition_saved", data: { key: "North", record_id: 4 } });
    await flushPromises();
    expect(api.liveOverview).toHaveBeenCalledWith("p1");
    page.unmount();
  });

  it("tier 1 全部指标 opens the shown live record and keeps it while newer records arrive (issue #106)", async () => {
    const api = takeoverApi(1, "running");
    api.acquisition.mockImplementation(async (key: string, id: number) => detail(id, key));
    const { store } = takeoverStore(api);
    await store.init();
    const overviewStore = createOverviewStore(api as unknown as ApiClient);
    const page = mount(OverviewPage, { props: { store: overviewStore, takeover: store } });
    await flushPromises();
    await page.get("[data-role=details-button]").trigger("click");
    await flushPromises();
    expect(api.acquisition).toHaveBeenCalledWith("p1", 3);
    const dialog = () => page.get("[data-role=details-dialog]");
    expect(dialog().attributes("aria-label")).toBe("全部指标 · #3 · 2026-10-18 09:29:00.000");
    expect(dialog().find("[data-key=lux]").exists()).toBe(true);
    // a newer record is saved and shown: the open dialog stays on #3, as V1.0.3's modal dialog does
    api.liveOverview.mockImplementation(async (key: string) => live(key, 4));
    store.onEvent({ id: 8, name: "acquisition_saved", data: { key: "North", record_id: 4 } });
    await flushPromises();
    expect(page.get("[data-role=status]").text()).toContain("显示 #4");
    expect(dialog().attributes("aria-label")).toBe("全部指标 · #3 · 2026-10-18 09:29:00.000");
    expect(overviewStore.shownDetail()?.record.id).toBe(3);
    await dialog().get(".buttons button").trigger("click");
    await page.get("[data-role=details-button]").trigger("click");
    await flushPromises();
    expect(api.acquisition).toHaveBeenLastCalledWith("p1", 4);
    expect(dialog().attributes("aria-label")).toBe("全部指标 · #4 · 2026-10-18 09:29:00.000");
    // another database at the position (the configuration was changed): the open dialog closes
    api.liveOverview.mockImplementation(async (key: string) => ({ ...live(key), snapshot_id: `${key}-other` }));
    await overviewStore.refreshLive();
    await flushPromises();
    expect(page.find("[data-role=details-dialog]").exists()).toBe(false);
    page.unmount();
  });

  it("tier 0 keeps the snapshot page without takeover controls", async () => {
    const api = takeoverApi(0);
    const { store } = takeoverStore(api);
    await store.init();
    const overviewStore = createOverviewStore(api as unknown as ApiClient);
    await overviewStore.showDevice("p1");
    const page = mount(OverviewPage, { props: { store: overviewStore, takeover: store } });
    await flushPromises();
    expect(page.get("[data-role=snapshot]").text()).toContain("快照数据，非实时");
    expect(page.find("[data-role=live]").exists()).toBe(false);
    expect(api.liveOverview).not.toHaveBeenCalled();
    page.unmount();
  });
});

describe("a takeover still running while the tier reads 0 (PR #54 review M2; D-215)", () => {
  /** The settings file became unreadable (or was set to 0) during a takeover: GET /tier answers tier 0 with the
   * takeover still running. The service keeps acquiring and still answers status and stop, so the pages must keep
   * the running state, the halt banner and 停止采集, and offer neither 开始采集 nor saving. */
  function heldOver() {
    const api = takeoverApi(0, "running");
    api.tier.mockResolvedValue({
      ...tierState(0, "running", "running"),
      settings_problem: "JSONDecodeError: Expecting value",
    });
    api.acquisitionStatus.mockResolvedValue(status("running", true));
    return api;
  }

  it("the store keeps reading the status while the takeover is not released", async () => {
    const { api, store } = takeoverStore(heldOver());
    await store.init();
    expect(api.acquisitionStatus).toHaveBeenCalled();
    expect(store.state.status.data?.takeover).toBe("running");
    expect(store.heldOver()).toBe(true);
  });

  it("the overview keeps the running state, the halt banner and 停止采集; no start, no live read", async () => {
    const api = heldOver();
    const { store } = takeoverStore(api);
    await store.init();
    const overviewStore = createOverviewStore(api as unknown as ApiClient);
    const page = mount(OverviewPage, { props: { store: overviewStore, takeover: store } });
    await flushPromises();
    expect(page.find("[data-role=live]").exists()).toBe(true);
    expect(page.get("[data-role=held-over]").text()).toContain("采集仍在运行");
    expect(page.get("[data-role=takeover-text]").text()).toBe(TEXTS.running![0]);
    expect(page.get("[data-role=start]").attributes("disabled")).toBeDefined();
    expect(page.get("[data-role=stop]").attributes("disabled")).toBeUndefined();
    expect(page.get("[data-role=halt]").text()).toContain("请为该设备重新上电");
    expect(api.liveOverview).not.toHaveBeenCalled();
    await page.get("[data-role=stop]").trigger("click");
    expect(store.state.dialog).toBe("stop");
    page.unmount();
  });

  it("the overview keeps the stop control when a reconnection re-reads tier 0 mid-takeover", async () => {
    const api = takeoverApi(1, "running");
    const { store } = takeoverStore(api);
    await store.init();
    const overviewStore = createOverviewStore(api as unknown as ApiClient);
    const page = mount(OverviewPage, { props: { store: overviewStore, takeover: store } });
    await flushPromises();
    expect(page.find("[data-role=live]").exists()).toBe(true);
    api.tier.mockResolvedValue({ ...tierState(0, "running", "running"), settings_problem: "PermissionError" });
    store.onStream("open");
    await flushPromises();
    expect(page.find("[data-role=live]").exists()).toBe(true);
    expect(page.get("[data-role=stop]").attributes("disabled")).toBeUndefined();
    expect(store.state.status.data?.takeover).toBe("running");
    page.unmount();
  });

  it("the tier panel offers 停止采集 instead of 开启档位 1 while the takeover is not released", async () => {
    const { store } = takeoverStore(heldOver());
    await store.init();
    const panel = mount(TierPanel, { props: { store } });
    expect(panel.find("[data-role=tier-up]").exists()).toBe(false);
    expect(panel.get("[data-role=tier-held-over]").text()).toContain("采集仍在运行");
    expect(panel.get("[data-role=settings-problem]").text()).toContain("JSONDecodeError");
    await panel.get("[data-role=tier-stop]").trigger("click");
    expect(store.state.dialog).toBe("stop");
    await store.confirmStop();
    expect(store.state.dialog).toBe("none");
  });
});

describe("an unusable configuration and a failed apply (spec review M-1, Q-1; D-220, D-221)", () => {
  const PROBLEM = { message: "无法读取采集配置：/alpha/config/app_config.json", detail: "Expecting value" };

  function unusable() {
    const api = takeoverApi(1, "released");
    api.acquisitionConfig.mockResolvedValue({ ...config(), problem: PROBLEM });
    return api;
  }

  it("offers 以空配置重新配置 with the service's texts; confirmed, the form is blank and the save asks to reconfigure", async () => {
    const api = unusable();
    const { store } = takeoverStore(api);
    await store.init();
    await store.loadConfig();
    const editor = mount(AcquisitionConfigEditor, { props: { store } });
    const dialogs = mount(TakeoverDialogs, { props: { store } });
    expect(editor.get("[data-role=config-problem]").text()).toContain(PROBLEM.message);
    expect(editor.get("[data-role=config-problem]").text()).toContain("配置或数据库不可用");
    await editor.get("[data-role=reconfigure]").trigger("click");
    expect(store.state.dialog).toBe("reconfigure");
    expect(dialogs.text()).toContain("是否以空配置重新配置？");
    expect(dialogs.text()).toContain(PROBLEM.message);
    expect(store.confirmReconfigure()).toBe(true);
    await flushPromises();
    expect(store.state.reconfiguring).toBe(true);
    expect(store.state.draft?.rows.map((row) => row.name)).toEqual(["", "", "", ""]);
    expect(store.state.draft?.bus.serial_port).toBe("");
    expect(editor.get("[data-role=reconfigure-hint]").text()).toContain("先备份原配置文件");
    store.setRow(0, "name", "North");
    store.setRow(0, "enabled", true);
    store.setBus("serial_port", "COM7");
    api.acquisitionConfig.mockResolvedValue(config());
    expect(await store.save()).toBe(true);
    const calls = api.saveAcquisitionConfig.mock.calls as unknown as [{ reconfigure: boolean; devices: { name: string }[] }][];
    expect(calls[0]![0].reconfigure).toBe(true);
    expect(calls[0]![0].devices[0]!.name).toBe("North");
    expect(store.state.reconfiguring).toBe(false);
  });

  it("cancelling keeps the form; 撤销修改 leaves the reconfiguration; without a problem nothing is offered", async () => {
    const api = unusable();
    const { store } = takeoverStore(api);
    await store.init();
    await store.loadConfig();
    store.askReconfigure();
    store.cancelDialog();
    expect(store.state.reconfiguring).toBe(false);
    expect(store.state.draft?.rows[0]?.name).toBe("North");
    store.askReconfigure();
    store.confirmReconfigure();
    store.resetDraft();
    expect(store.state.reconfiguring).toBe(false);
    expect(store.state.draft?.rows[0]?.name).toBe("North");

    const fine = takeoverStore(takeoverApi(1, "released"));
    await fine.store.init();
    await fine.store.loadConfig();
    const editor = mount(AcquisitionConfigEditor, { props: { store: fine.store } });
    expect(editor.find("[data-role=config-problem]").exists()).toBe(false);
    expect(fine.store.confirmReconfigure()).toBe(false);
    await fine.store.save();
    const calls = fine.api.saveAcquisitionConfig.mock.calls as unknown as [{ reconfigure: boolean }][];
    expect(calls[0]![0].reconfigure).toBe(false);
  });

  it("a start refused with config_unavailable reads the configuration again, so the way out shows", async () => {
    const api = takeoverApi(1, "released");
    api.startAcquisition.mockRejectedValueOnce(
      new ApiError(409, {
        code: "config_unavailable",
        message: "采集配置或设备库不可用，本次未开始采集。可在“设置与导出”……选择“以空配置重新配置…”",
        retryable: false,
        detail: "North.sqlite3 不存在",
      }),
    );
    const { store } = takeoverStore(api);
    await store.init();
    await store.loadConfig();
    api.acquisitionConfig.mockResolvedValue({ ...config(), problem: PROBLEM });
    expect(await store.start()).toBe(false);
    await flushPromises();
    expect(api.acquisitionConfig).toHaveBeenCalledTimes(2);
    expect(store.state.config.data?.problem).toEqual(PROBLEM);
  });

  it("a failed background apply is marked 未生效 and saving stays possible (deliberate deviation from DEF-31)", async () => {
    const api = takeoverApi();
    api.acquisitionStatus.mockResolvedValue({ ...status("running"), config_apply_error: "应用配置失败：disk went away" });
    const { store } = takeoverStore(api);
    await store.init();
    await store.loadConfig();
    store.setRow(1, "name", "South");
    expect(await store.save()).toBe(true);
    const editor = mount(AcquisitionConfigEditor, { props: { store } });
    const failed = editor.get("[data-role=apply-failed]");
    expect(failed.text()).toContain("未生效");
    expect(failed.text()).toContain("应用配置失败：disk went away");
    expect(editor.find("[data-role=config-saved]").exists()).toBe(false);
    expect(editor.get("[data-role=config-save]").attributes("disabled")).toBeUndefined();
  });
});
