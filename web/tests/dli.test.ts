import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "../src/api/client";
import App from "../src/App.vue";
import DliChart from "../src/components/DliChart.vue";
import DliPage from "../src/pages/DliPage.vue";
import { createCalcStore } from "../src/pages/calcStore";
import { createDliStore } from "../src/pages/dliStore";
import { createHistoryStore } from "../src/pages/historyStore";
import { createOverviewStore } from "../src/pages/overviewStore";
import { createSettingsStore } from "../src/pages/settingsStore";
import type { DliTick } from "../src/api/types";
import { axisNumber } from "../src/lib/axis";
import { axisEnd, curve, latestDate, midnightStagger, STAGGER_PX, tickText, visibleTicks } from "../src/lib/dli";
import { searchFor, viewFrom } from "../src/lib/view";
import { detail, devices, dliDay, dliMetric, health, item, jsonResponse, page, snapshots } from "./fixtures";

// happy-dom has no canvas: ECharts is replaced by a recorder of the options the chart component sets
const charts = vi.hoisted(() => ({ options: [] as unknown[] }));
vi.mock("echarts/core", () => ({
  use: () => undefined,
  init: () => ({
    setOption: (option: unknown) => charts.options.push(option),
    resize: () => undefined,
    dispose: () => undefined,
  }),
}));

/** Narrow-chart ticks of a period 10-01 01:57 → 10-02 01:57 (service `axis_ticks`, 6 h spacing). */
const LATE_MIDNIGHT: DliTick[] = [
  { offset_seconds: 0, at: "2026-10-01T01:57:00.000", text: "10-01\n01:57", narrow: true },
  { offset_seconds: 14580, at: "2026-10-01T06:00:00.000", text: "06:00", narrow: true },
  { offset_seconds: 36180, at: "2026-10-01T12:00:00.000", text: "12:00", narrow: true },
  { offset_seconds: 57780, at: "2026-10-01T18:00:00.000", text: "18:00", narrow: true },
  { offset_seconds: 79380, at: "2026-10-02T00:00:00.000", text: "10-02\n00:00", narrow: true },
  { offset_seconds: 86400, at: "2026-10-02T01:57:00.000", text: "10-02\n01:57", narrow: true },
];
/** Narrow-chart ticks of a period 10-01 22:54 → 10-02 22:54. */
const EARLY_MIDNIGHT: DliTick[] = [
  { offset_seconds: 0, at: "2026-10-01T22:54:00.000", text: "10-01\n22:54", narrow: true },
  { offset_seconds: 3960, at: "2026-10-02T00:00:00.000", text: "10-02\n00:00", narrow: true },
  { offset_seconds: 25560, at: "2026-10-02T06:00:00.000", text: "06:00", narrow: true },
  { offset_seconds: 47160, at: "2026-10-02T12:00:00.000", text: "12:00", narrow: true },
  { offset_seconds: 68760, at: "2026-10-02T18:00:00.000", text: "18:00", narrow: true },
  { offset_seconds: 86400, at: "2026-10-02T22:54:00.000", text: "10-02\n22:54", narrow: true },
];

const unavailable = () =>
  new ApiError(503, { code: "database_unavailable", message: "数据库不可访问：/alpha/p1.sqlite", retryable: true, detail: null });

function dliApi() {
  return {
    dli: vi.fn(async (key: string, date: string | null) => dliDay(key, date ?? "2026-10-18", date === null)),
    saveDliLocation: vi.fn(async (key: string, latitude: number, longitude: number, date: string | null) => {
      const day = dliDay(key, date ?? "2026-10-18", date === null);
      const text = "积分周期：2026-10-18 06:00 → 2026-10-19 06:00（北京时间，日出起算，固定24小时）";
      const coordinates = `纬度 ${latitude.toFixed(4)} °N，经度 ${longitude.toFixed(4)} °E`;
      return {
        ...day,
        period: { ...day.period, start: "2026-10-18T06:00:00.000", text },
        location: { ...day.location, latitude, longitude, stored: true, coordinates_text: coordinates },
      };
    }),
  };
}

function storeOf(api: ReturnType<typeof dliApi>) {
  return createDliStore(api as unknown as ApiClient);
}

describe("DLI client", () => {
  it("asks for the current period without a date and for a past one with ?date=", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, dliDay()));
    const api = new ApiClient("t", fetchImpl);
    await api.dli("p1");
    await api.dli("p 2", "2026-10-17");
    expect(fetchImpl.mock.calls.map((call) => (call as unknown[])[0])).toEqual([
      "/api/v0/devices/p1/dli",
      "/api/v0/devices/p%202/dli?date=2026-10-17",
    ]);
  });
});

describe("DLI store", () => {
  it("shows the current period of the viewed device and puts its start date in the picker", async () => {
    const api = dliApi();
    const store = storeOf(api);
    await store.showDevice("p1");
    expect(api.dli).toHaveBeenCalledWith("p1", null);
    expect(store.state.day.data?.period.current).toBe(true);
    expect(store.state.dateInput).toBe("2026-10-18");
  });

  it("applies a picked date only on 查看 and goes back with 当前周期", async () => {
    const api = dliApi();
    const store = storeOf(api);
    await store.showDevice("p1");
    store.state.dateInput = "2026-10-12";
    expect(api.dli).toHaveBeenCalledTimes(1);
    await store.applyDate();
    expect(api.dli).toHaveBeenLastCalledWith("p1", "2026-10-12");
    expect(store.state.day.data?.period.current).toBe(false);
    await store.showCurrent();
    expect(api.dli).toHaveBeenLastCalledWith("p1", null);
  });

  it("refuses an empty or malformed date without asking the service", async () => {
    const api = dliApi();
    const store = storeOf(api);
    await store.showDevice("p1");
    store.state.dateInput = "";
    expect(await store.applyDate()).toBe(false);
    expect(store.state.inputError).toContain("年-月-日");
    expect(api.dli).toHaveBeenCalledTimes(1);
  });

  it("keeps the last valid period when a reload fails and retries the same request (R-1-5)", async () => {
    const api = dliApi();
    const store = storeOf(api);
    await store.showDevice("p1");
    store.state.dateInput = "2026-10-12";
    await store.applyDate();
    api.dli.mockRejectedValueOnce(unavailable());
    await store.refresh();
    expect(store.state.day.error?.code).toBe("database_unavailable");
    expect(store.state.day.data?.period.date).toBe("2026-10-12");
    await store.state.day.retry?.();
    expect(api.dli).toHaveBeenLastCalledWith("p1", "2026-10-12");
    expect(store.state.day.error).toBeNull();
  });

  it("never shows one device's period as another's; the applied date is kept across devices", async () => {
    const api = dliApi();
    const store = storeOf(api);
    await store.showDevice("p1");
    store.state.dateInput = "2026-10-12";
    await store.applyDate();
    api.dli.mockRejectedValueOnce(unavailable());
    await store.showDevice("p2");
    expect(store.state.day.data).toBeNull();
    expect(store.state.day.error?.code).toBe("database_unavailable");
    expect(api.dli).toHaveBeenLastCalledWith("p2", "2026-10-12");
  });

  it("a background reload never overwrites a date the user is typing (review N-2)", async () => {
    const api = dliApi();
    const store = storeOf(api);
    await store.showDevice("p1");
    expect(store.state.dateInput).toBe("2026-10-18"); // untouched picker: kept in step
    store.state.dateInput = "2026-10-1"; // typing, 查看 not pressed
    await store.refresh(); // what the 30 s timer calls
    expect(store.state.dateInput).toBe("2026-10-1");
    await store.showCurrent(); // an explicit action syncs again
    expect(store.state.dateInput).toBe("2026-10-18");
  });

  it("with no device it asks nothing", async () => {
    const api = dliApi();
    const store = storeOf(api);
    expect(await store.showDevice(null)).toBe(false);
    expect(api.dli).not.toHaveBeenCalled();
  });
});

describe("DLI chart helpers", () => {
  it("passes the service's breaks on as null and never fills them", () => {
    expect(curve(dliMetric("ppfd", "t").series)).toEqual([
      [2010, 0],
      [2640, null],
      [2670, 1.2],
    ]);
    expect(curve(null)).toEqual([]);
  });

  it("shows every tick on a wide chart and only the 6-hour ones below 700 px (UI-183)", () => {
    const ticks = dliDay().ticks;
    expect(visibleTicks(ticks, 900)).toHaveLength(5);
    expect(visibleTicks(ticks, 699).map((tick) => tick.text)).toEqual(["10-18\n06:26", "12:00", "10-19\n00:00", "10-19\n06:26"]);
    expect(tickText(ticks, 63210)).toBe("10-19\n00:00");
    expect(axisEnd(ticks)).toBe(86400);
  });
});

describe("DLI chart and page", () => {
  it("puts the name left and the total right, then state, times and coverage as given (UI-180, UI-181)", () => {
    const wrapper = mount(DliChart, { props: { metric: dliMetric("ppfd", "PPFD-DLI（400–700 nm）"), ticks: [] } });
    expect(wrapper.get(".title").text()).toBe("PPFD-DLI（400–700 nm）");
    expect(wrapper.get(".total").text()).toBe("已累计：2.408 mol·m⁻²");
    expect(wrapper.get("[data-role=state]").classes()).toContain("state-warn");
    expect(wrapper.get("[data-role=coverage]").attributes("title")).toContain("起始未覆盖");
    expect(wrapper.find(".no-data").exists()).toBe(false);
  });

  it("draws the service's curve with breaks, a zero-based y axis and the service's ticks (UI-183, UI-184)", () => {
    charts.options.length = 0;
    mount(DliChart, { props: { metric: dliMetric("ppfd", "t"), ticks: dliDay().ticks } });
    const option = charts.options.at(-1) as {
      xAxis: {
        min: number;
        max: number;
        axisLabel: {
          customValues: number[];
          alignMinLabel: string;
          alignMaxLabel: string;
          formatter: (v: number) => string;
        };
      }[];
      yAxis: { min: number; max: number; axisLabel: { formatter: unknown } };
      series: { data: unknown[]; connectNulls: boolean }[];
    };
    expect([option.yAxis.min, option.yAxis.max]).toEqual([0, 2.769]);
    expect(option.yAxis.axisLabel.formatter).toBe(axisNumber); // issue 108: no floating-point residue
    // midnight is far from both ends: no staggered row, one x axis (UI-185)
    expect(option.xAxis).toHaveLength(1);
    const xAxis = option.xAxis[0]!;
    expect([xAxis.min, xAxis.max]).toEqual([0, 86400]);
    // the end labels sit inside the plot, so the period bounds stay readable (V1.0.3 anchors them the same way)
    expect([xAxis.axisLabel.alignMinLabel, xAxis.axisLabel.alignMaxLabel]).toEqual(["left", "right"]);
    expect(xAxis.axisLabel.customValues).toEqual([0, 20010, 63210, 86400]); // happy-dom width 0: narrow
    expect(xAxis.axisLabel.formatter(63210)).toBe("10-19\n00:00");
    expect(option.series[0]?.data).toEqual([
      [2010, 0],
      [2640, null],
      [2670, 1.2],
    ]);
    expect(option.series[0]?.connectNulls).toBe(false);
  });

  it("moves the midnight label one row down when it overlaps an end label, as V1.0.3 (UI-185)", async () => {
    const width = Object.getOwnPropertyDescriptor(HTMLElement.prototype, "clientWidth");
    Object.defineProperty(HTMLElement.prototype, "clientWidth", { configurable: true, get: () => 532 });
    try {
      charts.options.length = 0;
      // sunrise 01:57 Beijing time (a saved longitude of 174.76° E): midnight 1 h 57 min before the period end
      const wrapper = mount(DliChart, { props: { metric: dliMetric("ppfd", "t"), ticks: LATE_MIDNIGHT } });
      const option = charts.options.at(-1) as {
        grid: { bottom: number };
        xAxis: {
          nameGap?: number;
          offset?: number;
          axisLine?: { show: boolean };
          axisLabel: { customValues: number[]; align?: string; formatter: (v: number) => string };
        }[];
      };
      const [main, lowered] = option.xAxis;
      // the main axis keeps the tick but leaves the label to the lowered row
      expect(main?.axisLabel.customValues).toEqual([0, 14580, 36180, 57780, 79380, 86400]);
      expect(main?.axisLabel.formatter(79380)).toBe("");
      expect(main?.axisLabel.formatter(86400)).toBe("10-02\n01:57");
      expect(lowered).toMatchObject({ offset: STAGGER_PX, axisLine: { show: false } });
      expect(lowered?.axisLabel.customValues).toEqual([79380]);
      expect(lowered?.axisLabel.align).toBe("right"); // the overlapped neighbour is the end label
      expect(lowered?.axisLabel.formatter(79380)).toBe("10-02\n00:00");
      // V1.0.3 grows the bottom margin and the canvas by the same row (59 → 85 px, 210 → 236 px)
      expect(option.grid.bottom).toBe(48 + STAGGER_PX);
      expect(main?.nameGap).toBe(36 + STAGGER_PX);
      await flushPromises();
      expect(wrapper.get("[data-testid=dli-chart]").attributes("style")).toContain(`+ ${STAGGER_PX}px`);
    } finally {
      if (width) Object.defineProperty(HTMLElement.prototype, "clientWidth", width);
    }
  });

  it("decides the stagger from the label boxes like DliCanvas._layout_plot (UI-185)", () => {
    const byChars = (text: string) => Math.max(...text.split("\n").map((line) => line.length * 6.6));
    // 2 h before the end on a 444 px plot: 10-02 00:00 (centred, 33 px) runs into the right-anchored end label
    expect(midnightStagger(LATE_MIDNIGHT, 444, byChars)).toBe("right");
    // 1 h after the start: it runs into the left-anchored start label and is anchored left
    expect(midnightStagger(EARLY_MIDNIGHT, 444, byChars)).toBe("left");
    // a wide plot leaves room: no stagger, as on Chinese longitudes (midnight ≥ 4.5 h from the end)
    expect(midnightStagger(LATE_MIDNIGHT, 2000, byChars)).toBeNull();
    expect(midnightStagger(dliDay().ticks, 444, byChars)).toBeNull();
    // not laid out yet, or no midnight inside the period
    expect(midnightStagger(LATE_MIDNIGHT, 0, byChars)).toBeNull();
    expect(midnightStagger([LATE_MIDNIGHT[0]!, LATE_MIDNIGHT.at(-1)!], 444, byChars)).toBeNull();
  });

  it("says 有效数据不足 on a chart without coverage", () => {
    const wrapper = mount(DliChart, { props: { metric: dliMetric("x", "t", false), ticks: [] } });
    expect(wrapper.get(".no-data").text()).toBe("有效数据不足");
    expect(wrapper.get("[data-role=state]").classes()).toContain("state-muted");
  });

  it("shows period, four charts, interruptions and the read-only location; keeps them on a failure", async () => {
    const api = dliApi();
    const store = storeOf(api);
    await store.showDevice("p1");
    const wrapper = mount(DliPage, { props: { store }, global: { stubs: { DliChart: true } } });
    expect(wrapper.get("[data-role=period]").text()).toContain("日出起算，固定24小时");
    expect(wrapper.get("[data-role=period]").attributes("title")).toContain("已保存位置");
    expect(wrapper.findAll("dli-chart-stub")).toHaveLength(4);
    expect(wrapper.text()).toContain("恢复命令未确认");
    expect(wrapper.text()).toContain("纬度 39.9042 °N，经度 116.4074 °E");
    expect(wrapper.text()).toContain("（尚未保存，按默认北京坐标）");
    expect(wrapper.get<HTMLInputElement>("input[name=dli-latitude]").element.value).toBe("39.9042");
    expect(wrapper.get("[data-role=save-location]").text()).toBe("保存经纬度并重置周期");
    expect(wrapper.text()).toContain("允许间隔 360 秒（按轮询周期 300 秒计，取自 2026-10-18 09:25:00.000 的采集记录）");
    api.dli.mockRejectedValueOnce(unavailable());
    await store.refresh();
    await flushPromises();
    expect(wrapper.text()).toContain("数据库不可访问");
    expect(wrapper.text()).toContain("仍显示上次读取的结果");
    expect(wrapper.findAll("dli-chart-stub")).toHaveLength(4);
    await wrapper.get("[role=alert] button").trigger("click");
    await flushPromises();
    expect(wrapper.find("[role=alert]").exists()).toBe(false);
  });

  it("typing a location changes nothing; 保存经纬度并重置周期 saves it and shows the period again (issue 116)", async () => {
    const api = dliApi();
    const store = storeOf(api);
    await store.showDevice("p1");
    const wrapper = mount(DliPage, { props: { store }, global: { stubs: { DliChart: true } } });
    await wrapper.get("input[name=dli-latitude]").setValue("31.2304");
    await wrapper.get("input[name=dli-longitude]").setValue("121.4737");
    expect(api.saveDliLocation).not.toHaveBeenCalled(); // DLI-025: editing alone does not apply
    expect(wrapper.get("[data-role=period]").text()).toContain("06:26");
    await store.refresh(); // a background reload keeps what is being typed
    expect(String(store.state.latitudeInput)).toBe("31.2304");
    await wrapper.get("[data-role=location-form]").trigger("submit");
    await flushPromises();
    expect(api.saveDliLocation).toHaveBeenCalledWith("p1", 31.2304, 121.4737, null);
    expect(wrapper.get("[data-role=period]").text()).toContain("06:00");
    expect(wrapper.text()).toContain("（已保存）");
    expect(String(store.state.latitudeInput)).toBe("31.2304");
  });

  it("a refused save keeps the inputs as typed and the period as shown, with a retry (R-1-5)", async () => {
    const api = dliApi();
    const refusal = "只读模式不保存位置：请在“设置与导出”开启采集模式";
    api.saveDliLocation.mockRejectedValueOnce(
      new ApiError(403, { code: "feature_disabled", message: refusal, retryable: false, detail: null }),
    );
    const store = storeOf(api);
    await store.showDevice("p1");
    const wrapper = mount(DliPage, { props: { store }, global: { stubs: { DliChart: true } } });
    await wrapper.get("input[name=dli-latitude]").setValue("31.2304");
    await wrapper.get("[data-role=location-form]").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("只读模式不保存位置");
    expect(String(store.state.latitudeInput)).toBe("31.2304");
    expect(wrapper.get("[data-role=period]").text()).toContain("06:26");
    await wrapper.get("input[name=dli-latitude]").setValue("");
    await wrapper.get("[data-role=location-form]").trigger("submit");
    expect(wrapper.get("[data-role=location-error]").text()).toContain("请填写纬度和经度");
    expect(store.state.inputError).toBeNull(); // the date picker's own error line is not used
    expect(api.saveDliLocation).toHaveBeenCalledTimes(1);
  });

  it("a reload that read the old place before the save does not undo the saved period (review of PR #117)", async () => {
    const api = dliApi();
    const store = storeOf(api);
    await store.showDevice("p1");
    let answerOld: () => void = () => undefined;
    api.dli.mockImplementationOnce((key: string) => new Promise((resolve) => (answerOld = () => resolve(dliDay(key)))));
    const reload = store.refresh(); // the 30 s timer: still under way
    store.state.latitudeInput = "31.2304";
    store.state.longitudeInput = "121.4737";
    expect(await store.saveLocation()).toBe(true);
    answerOld();
    await reload;
    expect(store.state.day.data?.location.stored).toBe(true);
    expect(store.state.day.data?.period.text).toContain("06:00");
    expect(store.state.day.error).toBeNull();
  });

  it("another device fills the inputs with its own saved location", async () => {
    const api = dliApi();
    api.dli.mockImplementation(async (key: string) => {
      const day = dliDay(key);
      if (key !== "p2") return day;
      return { ...day, location: { ...day.location, latitude: 22.5431, longitude: 114.0579, stored: true } };
    });
    const store = storeOf(api);
    await store.showDevice("p1");
    expect(store.state.longitudeInput).toBe("116.4074");
    await store.showDevice("p2");
    expect([store.state.latitudeInput, store.state.longitudeInput]).toEqual(["22.5431", "114.0579"]);
  });

  it("limits the picker to as_of's day and names an applied date that failed to load (N-2, N-5)", async () => {
    const api = dliApi();
    const store = storeOf(api);
    await store.showDevice("p1");
    const wrapper = mount(DliPage, { props: { store }, global: { stubs: { DliChart: true } } });
    expect(wrapper.get("input[type=date]").attributes("max")).toBe("2026-10-18");
    api.dli.mockRejectedValueOnce(unavailable());
    store.state.dateInput = "2026-10-12";
    await store.applyDate();
    await flushPromises();
    // the page still shows the current period, while the store already holds the picked date
    expect(wrapper.get("[data-role=period]").text()).toContain("2026-10-18 06:26");
    expect(wrapper.text()).toContain("所选日期 2026-10-12 的周期尚未读取成功");
    await store.state.day.retry?.();
    await flushPromises();
    expect(wrapper.text()).not.toContain("尚未读取成功");
    expect(wrapper.get("[data-role=period]").text()).toContain("2026-10-12 06:26");
    wrapper.unmount();
  });

  it("keeps reloading the current-period view through the D-165 gap and moves on to the next period (DLI-041)", async () => {
    vi.useFakeTimers();
    try {
      const api = dliApi();
      const gap = { ...dliDay("p1", "2026-10-17", false), requested_date: null }; // the period that just ended
      api.dli.mockResolvedValueOnce(dliDay("p1", "2026-10-17")).mockResolvedValueOnce(gap);
      const store = storeOf(api);
      await store.showDevice("p1");
      const wrapper = mount(DliPage, { props: { store }, global: { stubs: { DliChart: true } } });
      await vi.advanceTimersByTimeAsync(30_000);
      expect(api.dli).toHaveBeenCalledTimes(2);
      expect(wrapper.get("[data-role=period]").text()).toContain("2026-10-17 06:26");
      expect(wrapper.find(".badge").exists()).toBe(false); // the current view, not a picked past period
      await vi.advanceTimersByTimeAsync(30_000);
      expect(api.dli).toHaveBeenCalledTimes(3);
      expect(api.dli).toHaveBeenLastCalledWith("p1", null);
      expect(wrapper.get("[data-role=period]").text()).toContain("2026-10-18 06:26");
      wrapper.unmount();
    } finally {
      vi.useRealTimers();
    }
  });

  it("marks only a picked period that has ended, and does not reload a finished one", async () => {
    vi.useFakeTimers();
    try {
      const api = dliApi();
      api.dli.mockImplementation(async (key: string, date: string | null) =>
        date === "2026-10-18" ? { ...dliDay(key, date), requested_date: date } : dliDay(key, date ?? "2026-10-18", date === null),
      );
      const store = storeOf(api);
      await store.showDevice("p1");
      store.state.dateInput = "2026-10-18";
      await store.applyDate(); // today: the period in progress
      const wrapper = mount(DliPage, { props: { store }, global: { stubs: { DliChart: true } } });
      expect(wrapper.find(".badge").exists()).toBe(false);
      await vi.advanceTimersByTimeAsync(30_000);
      expect(api.dli).toHaveBeenCalledTimes(3); // the period shown is in progress, so it moves on too
      store.state.dateInput = "2026-10-16";
      await store.applyDate();
      await flushPromises();
      expect(wrapper.get(".badge").text()).toBe("已结束的周期");
      await vi.advanceTimersByTimeAsync(60_000);
      expect(api.dli).toHaveBeenCalledTimes(4);
      wrapper.unmount();
    } finally {
      vi.useRealTimers();
    }
  });

  it("moves the picker's max past Beijing midnight while a finished period stays on screen (review M-1)", async () => {
    vi.useFakeTimers();
    try {
      const api = dliApi();
      api.dli.mockImplementation(async (key: string, date: string | null) => ({
        ...dliDay(key, date ?? "2026-10-18", date === null),
        as_of: "2026-10-18T23:59:10.000",
      }));
      const store = storeOf(api);
      await store.showDevice("p1");
      store.state.dateInput = "2026-10-16";
      await store.applyDate();
      const wrapper = mount(DliPage, { props: { store }, global: { stubs: { DliChart: true } } });
      expect(wrapper.get(".badge").text()).toBe("已结束的周期");
      expect(wrapper.get("input[type=date]").attributes("max")).toBe("2026-10-18");
      await vi.advanceTimersByTimeAsync(60_000);
      expect(api.dli).toHaveBeenCalledTimes(2); // a finished period is still not reloaded
      expect(wrapper.get("input[type=date]").attributes("max")).toBe("2026-10-19");
      store.state.dateInput = "2026-10-19";
      expect(await store.applyDate()).toBe(true);
      expect(api.dli).toHaveBeenLastCalledWith("p1", "2026-10-19");
      wrapper.unmount();
    } finally {
      vi.useRealTimers();
    }
  });
});

describe("latest pickable date", () => {
  it("is the Beijing day of as_of plus the time elapsed since it arrived, never the browser's own date", () => {
    expect(latestDate("2026-10-18T09:30:15.123", 0)).toBe("2026-10-18");
    expect(latestDate("2026-10-18T23:59:10.000", 49_999)).toBe("2026-10-18");
    expect(latestDate("2026-10-18T23:59:10.000", 50_000)).toBe("2026-10-19");
    expect(latestDate("2026-12-31T23:00:00.000", 2 * 3_600_000)).toBe("2027-01-01");
    expect(latestDate("2026-10-18T09:30:15.123", -5)).toBe("2026-10-18"); // a clock step back never moves it back
  });
});

describe("navigation", () => {
  it("reads and writes ?view= and keeps other parameters", () => {
    expect(viewFrom("?view=dli")).toBe("dli");
    expect(viewFrom("?view=x")).toBe("history");
    expect(searchFor("?a=1", "dli")).toBe("?a=1&view=dli");
    expect(searchFor("?view=dli", "history")).toBe("");
  });

  it("switches between history and DLI with the same viewed device", async () => {
    const api = {
      health: vi.fn(async () => health()),
      snapshots: vi.fn(async () => snapshots()),
      devices: vi.fn(async () => devices(["p1", "p2"])),
      acquisitions: vi.fn(async () => page([item(2, "2026-10-18T08:00:00.000")])),
      acquisition: vi.fn(async (_key: string, id: number) => detail(id)),
      importSnapshot: vi.fn(),
      ...dliApi(),
    };
    const store = createHistoryStore(api as unknown as ApiClient);
    const dli = createDliStore(api as unknown as ApiClient);
    const calc = createCalcStore(api as unknown as ApiClient);
    const wrapper = mount(App, {
      props: { store, dli, calc, settings: createSettingsStore(api as unknown as ApiClient), overview: createOverviewStore(api as unknown as ApiClient) },
      global: { stubs: { SpectrumChart: true, DliChart: true } },
    });
    await flushPromises();
    expect(wrapper.find("main.history").exists()).toBe(true);
    await wrapper.get("[data-view=dli]").trigger("click");
    await flushPromises();
    expect(wrapper.find("main.dli").exists()).toBe(true);
    expect(api.dli).toHaveBeenLastCalledWith("p1", null);
    await store.selectDevice("p2");
    await flushPromises();
    expect(api.dli).toHaveBeenLastCalledWith("p2", null);
    await wrapper.get("[data-view=history]").trigger("click");
    await flushPromises();
    expect(wrapper.find("main.history").exists()).toBe(true);
    expect(store.state.deviceKey).toBe("p2");
  });

  it("opens on the DLI page with ?view=dli", async () => {
    const api = {
      health: vi.fn(async () => health()),
      snapshots: vi.fn(async () => snapshots()),
      devices: vi.fn(async () => devices(["p1"])),
      acquisitions: vi.fn(async () => page([])),
      acquisition: vi.fn(),
      importSnapshot: vi.fn(),
      ...dliApi(),
    };
    const store = createHistoryStore(api as unknown as ApiClient);
    const dli = createDliStore(api as unknown as ApiClient);
    const calc = createCalcStore(api as unknown as ApiClient);
    const wrapper = mount(App, {
      props: { store, dli, calc, settings: createSettingsStore(api as unknown as ApiClient), overview: createOverviewStore(api as unknown as ApiClient), initialView: "dli" },
      global: { stubs: { SpectrumChart: true, DliChart: true } },
    });
    await flushPromises();
    expect(wrapper.find("main.dli").exists()).toBe(true);
    expect(api.dli).toHaveBeenCalledTimes(1);
  });
});
