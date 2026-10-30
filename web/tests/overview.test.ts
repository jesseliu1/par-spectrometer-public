import { flushPromises, mount } from "@vue/test-utils";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "../src/api/client";
import App from "../src/App.vue";
import OverviewChart from "../src/components/OverviewChart.vue";
import OverviewPage from "../src/pages/OverviewPage.vue";
import PageNav from "../src/components/PageNav.vue";
import { createCalcStore } from "../src/pages/calcStore";
import { createDliStore } from "../src/pages/dliStore";
import { createHistoryStore } from "../src/pages/historyStore";
import { createOverviewStore } from "../src/pages/overviewStore";
import { createSettingsStore } from "../src/pages/settingsStore";
import { NO_DEVICE_TEXT, searchFor, viewFrom } from "../src/lib/view";
import { detail, devices, health, jsonResponse, overview, page, snapshots } from "./fixtures";

// happy-dom has no canvas: ECharts is replaced by a recorder of the options the chart component sets
const charts = vi.hoisted(() => ({ options: [] as Record<string, unknown>[] }));
vi.mock("echarts/core", () => ({
  use: () => undefined,
  init: () => ({
    setOption: (option: Record<string, unknown>) => charts.options.push(option),
    resize: () => undefined,
    dispose: () => undefined,
  }),
}));

const unavailable = () =>
  new ApiError(503, { code: "database_unavailable", message: "数据库不可访问：/alpha/p1.sqlite", retryable: true, detail: null });

function overviewApi() {
  return {
    overview: vi.fn(async (key: string) => overview(key)),
    acquisition: vi.fn(async (key: string, id: number) => detail(id, key)),
  };
}

function store(api = overviewApi()) {
  return { api, overview: createOverviewStore(api as unknown as ApiClient) };
}

describe("overview store (API-09, D-211)", () => {
  it("loads the viewed device and keeps another device's answer off screen", async () => {
    const { api, overview: s } = store();
    await s.showDevice("p1");
    expect(api.overview).toHaveBeenLastCalledWith("p1");
    expect(s.state.overview.data?.display_record?.id).toBe(7);
    await s.showDevice("p2");
    expect(api.overview).toHaveBeenLastCalledWith("p2");
    expect(s.state.overview.data?.device.key).toBe("p2");
  });

  it("drops a slow answer for the previous device (UI-040)", async () => {
    let release: () => void = () => undefined;
    const api = overviewApi();
    api.overview.mockImplementationOnce(
      (key: string) => new Promise((done) => (release = () => done(overview(key, 3)))),
    );
    const { overview: s } = store(api);
    const first = s.showDevice("p1");
    await s.showDevice("p2");
    release();
    await first;
    expect(s.state.overview.data?.device.key).toBe("p2");
  });

  it("keeps the last overview when a reload fails, and the retry reloads (R-1-5)", async () => {
    const { api, overview: s } = store();
    await s.showDevice("p1");
    api.overview.mockRejectedValueOnce(unavailable());
    expect(await s.refresh()).toBe(false);
    expect(s.state.overview.error?.code).toBe("database_unavailable");
    expect(s.state.overview.data?.display_record?.id).toBe(7);
    expect(await s.state.overview.retry?.()).toBe(true);
    expect(s.state.overview.error).toBeNull();
  });

  it("without a device shows nothing and asks nothing", async () => {
    const { api, overview: s } = store();
    await s.showDevice(null);
    expect(api.overview).not.toHaveBeenCalled();
    expect(s.state.overview.data).toBeNull();
  });

  it("全部指标 loads the shown record's 54 values once (UI-009) and is refused without a record (UI-013)", async () => {
    const { api, overview: s } = store();
    await s.showDevice("p1");
    expect(await s.openDetails()).toBe(true);
    expect(api.acquisition).toHaveBeenCalledWith("p1", 7);
    expect(s.state.detailsId).toBe(7);
    s.closeDetails();
    expect(await s.openDetails()).toBe(true);
    expect(api.acquisition).toHaveBeenCalledTimes(1); // already loaded
    api.overview.mockResolvedValueOnce(overview("p1", null));
    await s.refresh();
    s.closeDetails();
    expect(await s.openDetails()).toBe(false);
    expect(s.state.detailsId).toBeNull();
  });

  it("全部指标 cache is per snapshot: a re-imported snapshot with the same #7 is asked again (评审 #53-2)", async () => {
    const { api, overview: s } = store();
    await s.showDevice("p1");
    expect(await s.openDetails()).toBe(true);
    s.closeDetails();
    api.overview.mockResolvedValue({ ...overview("p1"), snapshot_id: "p1-snap2" });
    api.acquisition.mockImplementation(async (key: string, id: number) => ({ ...detail(id, key), snapshot_id: "p1-snap2" }));
    await s.refresh();
    expect(await s.openDetails()).toBe(true);
    expect(api.acquisition).toHaveBeenCalledTimes(2);
    expect(s.shownDetail()?.snapshot_id).toBe("p1-snap2");
  });

  it("another device's 全部指标 is never shown for the same record id, even when its own load fails", async () => {
    const { api, overview: s } = store();
    await s.showDevice("p1");
    await s.openDetails();
    expect(s.shownDetail()?.device.key).toBe("p1");
    await s.showDevice("p2");
    api.acquisition.mockRejectedValueOnce(unavailable());
    expect(await s.openDetails()).toBe(false);
    expect(s.state.detailsId).toBe(7);
    expect(s.shownDetail()).toBeNull();
    expect(s.state.details.data).toBeNull();
  });

  it("a detail answered for an older snapshot is not shown for the new one", async () => {
    const { api, overview: s } = store();
    await s.showDevice("p1");
    api.overview.mockResolvedValue({ ...overview("p1"), snapshot_id: "p1-snap2" });
    await s.refresh();
    expect(await s.openDetails()).toBe(true); // the service answered p1-snap (fixture): not the shown snapshot
    expect(s.shownDetail()).toBeNull();
  });

  it("a re-imported snapshot closes the open dialog and forgets its values", async () => {
    const { api, overview: s } = store();
    await s.showDevice("p1");
    await s.openDetails();
    api.overview.mockResolvedValue({ ...overview("p1"), snapshot_id: "p1-snap2" });
    await s.refresh();
    expect(s.state.detailsId).toBeNull();
    expect(s.state.details.data).toBeNull();
  });

  it("switching device closes the dialog", async () => {
    const { overview: s } = store();
    await s.showDevice("p1");
    await s.openDetails();
    await s.showDevice("p2");
    expect(s.state.detailsId).toBeNull();
  });

  it("live 全部指标 loads the shown live record from the same database; another live device closes it (#106)", async () => {
    const api = {
      ...overviewApi(),
      liveOverview: vi.fn(async (key: string) => ({
        ...overview(key),
        source: "live" as const,
        device: { key, name: "North", database_path: `/alpha/data/devices/${key}.sqlite3` },
        paused: false,
      })),
    };
    const { overview: s } = store(api);
    await s.showLive("p1");
    expect(await s.openDetails()).toBe(false); // no tier-0 overview shown
    expect(await s.openDetails(true)).toBe(true);
    expect(api.acquisition).toHaveBeenCalledWith("p1", 7);
    expect(s.state.detailsFor?.title).toBe("全部指标 · #7 · 2026-10-18 09:29:00.000");
    expect(s.shownDetail()?.record.id).toBe(7);
    await s.showLive("p2");
    expect(s.state.detailsId).toBeNull();
    expect(s.shownDetail()).toBeNull();
  });

  it("显示指标 starts checked and is not stored (UI-061)", () => {
    const { overview: s } = store();
    expect(s.state.metricsVisible).toBe(true);
    s.setMetricsVisible(false);
    expect(s.state.metricsVisible).toBe(false);
    expect(createOverviewStore(overviewApi() as unknown as ApiClient).state.metricsVisible).toBe(true);
  });
});

describe("overview tab (D-211 question 1, superseded by issue #82)", () => {
  it("carries no 快照 tag any more: no page shows imported snapshots", () => {
    for (const view of ["overview", "history"] as const) {
      const nav = mount(PageNav, { props: { view } });
      expect(nav.find("[data-role=snapshot-tag]").exists()).toBe(false);
      expect(nav.get("[data-view=overview]").text()).toBe("实时概览");
    }
  });
});

describe("overview page", () => {
  beforeEach(() => {
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
  });

  async function shownPage(api = overviewApi(), key: string | null = "p1") {
    const s = createOverviewStore(api as unknown as ApiClient);
    await s.showDevice(key);
    const wrapper = mount(OverviewPage, { props: { store: s }, global: { stubs: { OverviewChart: true } } });
    await flushPromises();
    return { s, wrapper, api };
  }

  it("says it is a snapshot and shows the service's cards and status line as given", async () => {
    const { wrapper } = await shownPage();
    expect(wrapper.get("[data-role=snapshot]").text()).toContain("快照数据，非实时");
    const cards = wrapper.findAll("[data-role=kpis] .kpi");
    expect(cards.map((card) => card.get(".label").text())).toEqual([
      "照度",
      "350–1050 nm 总辐照度",
      "PPFD",
      "McCree-YPFD",
      "叶绿素 A 加权光子通量",
      "叶绿素 B 加权光子通量",
    ]);
    expect(cards[0]?.get(".value").text()).toBe("1234.5 lx");
    const status = wrapper.get("[data-role=status]");
    expect(status.text()).toBe(overview().status.text);
    expect(status.attributes("title")).toBe(overview().status.text); // UI-056: full text on hover
    expect(status.classes()).toContain("ok");
    expect(wrapper.text()).toContain("最新光谱");
  });

  it("has no acquisition, bus or start / stop control (tier 0)", async () => {
    const { wrapper } = await shownPage();
    for (const label of ["开始采集", "停止采集", "开始", "停止"]) {
      expect(wrapper.findAll("button").some((button) => button.text() === label)).toBe(false);
    }
    expect(wrapper.text()).not.toContain("总线");
    expect(wrapper.findAll("button").map((button) => button.text())).toEqual(["全部指标"]);
  });

  it("a failed round is red and keeps the record (UI-055)", async () => {
    const api = overviewApi();
    api.overview.mockResolvedValue(overview("p1", 7, { failedRound: true }));
    const { wrapper } = await shownPage(api);
    expect(wrapper.get("[data-role=status]").classes()).toContain("error");
    expect(wrapper.get("[data-role=status]").text()).toContain("本轮失败 · 保留最近有效数据");
  });

  it("disables 全部指标 without a record (UI-013)", async () => {
    const api = overviewApi();
    api.overview.mockResolvedValue(overview("p1", null));
    const { wrapper } = await shownPage(api);
    expect(wrapper.get("[data-role=details-button]").attributes("disabled")).toBeDefined();
    expect(wrapper.findAll("[data-role=kpis] .value").map((node) => node.text())).toEqual(Array(6).fill("—"));
  });

  it("shows the metrics error next to the cards it left (#38, D-211)", async () => {
    const api = overviewApi();
    api.overview.mockResolvedValue(overview("p1", 7, { metricsError: true }));
    const { wrapper } = await shownPage(api);
    expect(wrapper.get("[data-role=metrics-error]").text()).toContain("记录 #7 的指标数据无法解析");
    expect(wrapper.findAll("[data-role=kpis] .value").map((node) => node.text()).slice(0, 3)).toEqual([
      "1234.5 lx",
      "701.000 W/m²",
      "—",
    ]);
  });

  it("opens 全部指标 with the V1.0.3 title and columns and closes it", async () => {
    const { wrapper, api } = await shownPage();
    await wrapper.get("[data-role=details-button]").trigger("click");
    await flushPromises();
    const dialog = wrapper.get("[data-role=details-dialog]");
    expect(dialog.attributes("aria-label")).toBe("全部指标 · #7 · 2026-10-18 09:29:00.000");
    expect(dialog.findAll("thead th").map((node) => node.text())).toEqual(["指标", "数值", "单位"]);
    expect(dialog.get("tr.group").text()).toBe("常用光量");
    expect(dialog.get("[data-key=lux]").text()).toContain("1234.5");
    expect(api.acquisition).toHaveBeenCalledWith("p1", 7);
    await dialog.get(".buttons button").trigger("click");
    expect(wrapper.find("[data-role=details-dialog]").exists()).toBe(false);
  });

  it("a failed 全部指标 load offers a retry", async () => {
    const api = overviewApi();
    api.acquisition.mockRejectedValueOnce(unavailable());
    const { wrapper } = await shownPage(api);
    await wrapper.get("[data-role=details-button]").trigger("click");
    await flushPromises();
    const dialog = wrapper.get("[data-role=details-dialog]");
    expect(dialog.get("[role=alert]").text()).toContain("数据库不可访问");
    await dialog.get("[role=alert] button").trigger("click");
    await flushPromises();
    expect(wrapper.get("[data-role=details-dialog]").find("[data-key=lux]").exists()).toBe(true);
  });

  it("keeps the shown overview with a retry when a reload fails (R-1-5)", async () => {
    const { wrapper, api, s } = await shownPage();
    api.overview.mockRejectedValueOnce(unavailable());
    await s.refresh();
    await flushPromises();
    expect(wrapper.get("[role=alert]").text()).toContain("仍显示上次读取的 #7");
    expect(wrapper.get("[data-role=status]").text()).toContain("显示 #7");
  });

  it("reloads every 3 s while shown so the age moves on, and stops when gone", async () => {
    const { wrapper, api } = await shownPage();
    expect(api.overview).toHaveBeenCalledTimes(1);
    await vi.advanceTimersByTimeAsync(3000);
    expect(api.overview).toHaveBeenCalledTimes(2);
    wrapper.unmount();
    await vi.advanceTimersByTimeAsync(9000);
    expect(api.overview).toHaveBeenCalledTimes(2);
  });

  it("says how to get device data when there is no device (issue #82)", async () => {
    const { wrapper } = await shownPage(overviewApi(), null);
    expect(wrapper.get("[data-role=no-device]").text()).toBe(NO_DEVICE_TEXT);
    expect(wrapper.find("[data-role=summary]").exists()).toBe(false);
  });

  it("says tier 0 reads no device data whatever the data state: no device, or a failed first load", async () => {
    const empty = await shownPage(overviewApi(), null);
    expect(empty.wrapper.get("[data-role=snapshot]").text()).toBe("只读模式：不读取设备数据");
    const api = overviewApi();
    api.overview.mockRejectedValueOnce(unavailable());
    const failed = await shownPage(api);
    expect(failed.wrapper.find("[data-role=summary]").exists()).toBe(false);
    expect(failed.wrapper.get("[data-role=snapshot]").text()).toBe("只读模式：不读取设备数据");
  });

  it("does not ask again while a load is still running when the 3 s timer fires", async () => {
    const api = overviewApi();
    const { wrapper } = await shownPage(api);
    api.overview.mockImplementationOnce(() => new Promise(() => undefined));
    await vi.advanceTimersByTimeAsync(3000);
    expect(api.overview).toHaveBeenCalledTimes(2);
    await vi.advanceTimersByTimeAsync(9000);
    expect(api.overview).toHaveBeenCalledTimes(2);
    wrapper.unmount();
  });

  it("never shows another device's answer as the viewed device's", async () => {
    const { wrapper, s } = await shownPage();
    expect(wrapper.find("[data-role=summary]").exists()).toBe(true);
    s.state.deviceKey = "p2"; // the store still holds p1's answer
    await flushPromises();
    expect(wrapper.find("[data-role=summary]").exists()).toBe(false);
    wrapper.unmount();
  });
});

describe("overview chart", () => {
  it("draws the service's values from 0 to y_max with the fixed ticks (UI-057, UI-175)", () => {
    const data = overview();
    charts.options.length = 0;
    mount(OverviewChart, { props: { chart: data.chart, texts: data.texts, metricsVisible: true } });
    const option = charts.options.at(-1) as {
      xAxis: { min: number; max: number; name: string; axisLabel: { customValues: number[] } };
      yAxis: { min: number; max: number; name: string };
      series: { data: number[][] }[];
    };
    expect([option.xAxis.min, option.xAxis.max, option.xAxis.name]).toEqual([350, 1050, "波长 (nm)"]);
    expect(option.xAxis.axisLabel.customValues).toEqual([350, 400, 500, 600, 700, 800, 900, 1000, 1050]);
    expect([option.yAxis.min, option.yAxis.max, option.yAxis.name]).toEqual([0, 2 / 0.618, "功率 (mW/nm)"]);
    expect(option.series[0]?.data).toEqual([
      [350, 1],
      [351, 2],
    ]);
    const empty = overview("p1", null);
    mount(OverviewChart, { props: { chart: empty.chart, texts: empty.texts, metricsVisible: true } });
    expect((charts.options.at(-1) as { series: unknown[] }).series).toEqual([]);
  });

  it("shows the in-chart card in two columns behind 显示指标 (UI-060, UI-061)", () => {
    const data = overview();
    const wrapper = mount(OverviewChart, { props: { chart: data.chart, texts: data.texts, metricsVisible: true } });
    const columns = wrapper.findAll("[data-role=overlay] .column");
    expect(columns.map((column) => column.findAll(".row").length)).toEqual([1, 2]);
    expect(columns[1]?.text()).toContain("一般显色指数 Ra—");
    const hidden = mount(OverviewChart, { props: { chart: data.chart, texts: data.texts, metricsVisible: false } });
    expect(hidden.find("[data-role=overlay]").exists()).toBe(false);
  });

  it("an empty chart shows the service's title and the V1.0.3 empty texts (UI-054)", () => {
    const data = overview("p1", null);
    const wrapper = mount(OverviewChart, { props: { chart: data.chart, texts: data.texts, metricsVisible: true } });
    const empty = wrapper.get("[data-role=chart-empty]");
    expect(empty.text()).toContain("当前设备暂无可显示光谱");
    expect(empty.text()).toContain("暂无可显示的光谱");
    expect(empty.text()).toContain("选择有效采集记录后将在此显示曲线");
  });

  it("an unusable spectrum says so with the service's text (contract 1.2)", () => {
    const data = overview("p1", null);
    const chart = { ...data.chart, spectrum_state: "invalid" as const };
    const texts = { ...data.texts, invalid_spectrum: "服务给的无法解析文字" };
    const wrapper = mount(OverviewChart, { props: { chart, texts, metricsVisible: true } });
    expect(wrapper.get("[data-role=chart-empty]").text()).toContain("服务给的无法解析文字");
  });
});

describe("overview in the app", () => {
  it("is the first tab (UI-124) and follows the top bar's device", async () => {
    const api = {
      health: vi.fn(async () => health()),
      snapshots: vi.fn(async () => snapshots()),
      devices: vi.fn(async () => devices(["p1", "p2"])),
      acquisitions: vi.fn(async () => page([])),
      acquisition: vi.fn(async (key: string, id: number) => detail(id, key)),
      importSnapshot: vi.fn(),
      overview: vi.fn(async (key: string) => overview(key)),
    };
    const client = api as unknown as ApiClient;
    const store = createHistoryStore(client);
    const wrapper = mount(App, {
      props: {
        store,
        dli: createDliStore(client),
        calc: createCalcStore(client),
        settings: createSettingsStore(client),
        overview: createOverviewStore(client),
        initialView: "overview",
      },
      global: { stubs: { SpectrumChart: true, OverviewChart: true } },
    });
    await flushPromises();
    expect(wrapper.findAll("nav.tabs button .label").map((node) => node.text())[0]).toBe("实时概览");
    expect(wrapper.find("main.overview").exists()).toBe(true);
    expect(api.overview).toHaveBeenLastCalledWith("p1");
    await store.selectDevice("p2");
    await flushPromises();
    expect(api.overview).toHaveBeenLastCalledWith("p2");
    expect(wrapper.get("[data-role=status]").text()).toContain("显示 #7");
    wrapper.unmount();
  });

  it("keeps ?view=overview in the address; history stays the default page", () => {
    expect(viewFrom("?view=overview")).toBe("overview");
    expect(viewFrom("")).toBe("history");
    expect(searchFor("", "overview")).toBe("?view=overview");
  });

  it("the client asks /devices/{key}/latest", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, overview("p2")));
    const client = new ApiClient("t", fetchImpl);
    await client.overview("p2");
    expect(fetchImpl).toHaveBeenCalledWith("/api/v0/devices/p2/latest", expect.objectContaining({ method: "GET" }));
  });
});
