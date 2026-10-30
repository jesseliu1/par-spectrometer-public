import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { ApiError, type ApiClient } from "../src/api/client";
import DetailPanel from "../src/components/DetailPanel.vue";
import ErrorNotice from "../src/components/ErrorNotice.vue";
import KpiCards from "../src/components/KpiCards.vue";
import RecordTable from "../src/components/RecordTable.vue";
import StatusLine from "../src/components/StatusLine.vue";
import AboutPanel from "../src/components/AboutPanel.vue";
import { buildLabel } from "../src/lib/brand";
import TopBar from "../src/components/TopBar.vue";
import { runStatusView } from "../src/lib/runStatus";
import App from "../src/App.vue";
import HistoryPage from "../src/pages/HistoryPage.vue";
import { createCalcStore } from "../src/pages/calcStore";
import { createDliStore } from "../src/pages/dliStore";
import { createHistoryStore } from "../src/pages/historyStore";
import { createOverviewStore } from "../src/pages/overviewStore";
import { createReferenceStore } from "../src/pages/referenceStore";
import { createSettingsStore } from "../src/pages/settingsStore";
import { KPI_KEYS, kpis } from "../src/lib/kpis";
import { positionNumber, serviceTime } from "../src/lib/view";
import { axisRange, spectrumSeries } from "../src/lib/spectrum";
import { detail, devices, health, item, page, referenceCurves, snapshots } from "./fixtures";

describe("ErrorNotice", () => {
  it("shows the reason, what is kept, and a retry only when retryable", async () => {
    const error = new ApiError(503, { code: "database_unavailable", message: "库不可访问", retryable: true, detail: "p1.sqlite" });
    const wrapper = mount(ErrorNotice, { props: { error, keeping: "仍显示上次查询结果" } });
    expect(wrapper.text()).toContain("库不可访问");
    expect(wrapper.text()).toContain("仍显示上次查询结果");
    await wrapper.get("button").trigger("click");
    expect(wrapper.emitted("retry")).toHaveLength(1);
    const fixed = new ApiError(400, { code: "invalid_argument", message: "参数错误", retryable: false, detail: null });
    expect(mount(ErrorNotice, { props: { error: fixed } }).find("button").exists()).toBe(false);
    expect(mount(ErrorNotice, { props: { error: null } }).html()).not.toContain("alert");
  });
});

describe("RecordTable", () => {
  const items = page([item(9, "2026-10-18T09:00:00.000", false), item(8, "2026-10-18T08:00:00.000")]).items;

  it("lists the five columns as given and marks the selected row", () => {
    const wrapper = mount(RecordTable, { props: { items, selectedId: 8 } });
    expect(wrapper.findAll("th").map((th) => th.text())).toEqual([
      "序号",
      "ID",
      "采集时间（北京时间）",
      "采集结果",
      "曝光状态",
    ]);
    const rows = wrapper.findAll("tbody tr");
    expect(rows[0]?.findAll("td").map((td) => td.text())).toEqual(["1", "9", "2026-10-18 09:00:00.000", "失败", "未知"]);
    expect(rows[1]?.classes()).toContain("selected");
    expect(rows[0]?.find(".warn").exists()).toBe(true);
  });

  it("selects by click, Enter and arrow keys", async () => {
    const wrapper = mount(RecordTable, { props: { items, selectedId: 9 }, attachTo: document.body });
    await wrapper.findAll("tbody tr")[1]?.trigger("click");
    await wrapper.findAll("tbody tr")[0]?.trigger("keydown", { key: "ArrowDown" });
    expect(wrapper.emitted("select")).toEqual([[8], [8]]);
    wrapper.unmount();
  });

  it("says so when the range has no record", () => {
    expect(mount(RecordTable, { props: { items: [], selectedId: null } }).text()).toContain("所选范围内没有记录");
  });
});

describe("metric cards and detail", () => {
  it("picks the six UI-012 values by key and shows the service texts; a missing one is —", () => {
    const cards = kpis(detail(1).groups);
    expect(cards.map((card) => card.key)).toEqual([...KPI_KEYS]);
    expect(cards[0]).toMatchObject({ label: "照度", text: "1234.5", unit: "lx" });
    expect(cards[5]).toMatchObject({ key: "chlorophyll_b_ypfd", text: "—" });
    const wrapper = mount(KpiCards, { props: { groups: detail(1, "p1", false).groups } });
    expect(wrapper.findAll(".value").map((v) => v.text())).toEqual(["—", "—", "—", "—", "—", "—"]);
    expect(wrapper.findAll(".unit").every((unit) => unit.text() === "")).toBe(true);
  });

  it("shows header, elapsed and review even for a failed record (UI-030, UI-036)", () => {
    const wrapper = mount(DetailPanel, { props: { detail: detail(4, "p1", false) } });
    expect(wrapper.text()).toContain("记录详情 · 设备1 · #4");
    expect(wrapper.text()).toContain("5464.7");
    expect(wrapper.text()).toContain("单次读取完成");
    expect(wrapper.findAll(".item dd").every((dd) => dd.text() === "—")).toBe(true);
    expect(mount(DetailPanel, { props: { detail: null } }).text()).toContain("未选择记录");
  });

  it("plots the service's values against wavelength and keeps the 350–1050 nm axis without data", () => {
    const spectrum = detail(1).spectrum;
    expect(spectrumSeries(spectrum)).toEqual([
      [350, 1],
      [351, 2],
      [352, 3],
    ]);
    expect(axisRange(null)).toEqual([350, 1050]);
  });

  it("the status line says read-only, no device, in tier 0", () => {
    const wrapper = mount(StatusLine, { props: { asOf: null, sourceText: null, tier: 0 } });
    expect(wrapper.text()).toContain("只读模式 · 不连接设备");
  });

  it("before anything is read the status line says it is reading, not read-only (issue 119)", () => {
    const wrapper = mount(StatusLine, { props: { asOf: null, sourceText: null, tier: null } });
    expect(wrapper.get("[data-role=tier-fallback]").text()).toBe("正在读取状态…");
    expect(wrapper.text()).not.toContain("只读");
  });

  it("before the service's mode text is known, tier 1 and 2 are named alone (no read-only text beside them)", () => {
    for (const [tier, name] of [
      [1, "采集模式"],
      [2, "维护模式"],
    ] as const) {
      const wrapper = mount(StatusLine, { props: { asOf: null, sourceText: null, tier } });
      expect(wrapper.get("[data-role=tier-fallback]").text()).toBe(name);
      expect(wrapper.text()).not.toContain("只读模式");
    }
  });

  it("the service time reads as Beijing date and time, without T and milliseconds (alpha.5)", () => {
    const wrapper = mount(StatusLine, { props: { asOf: "2026-10-27T13:41:21.562", sourceText: null, tier: 0 } });
    expect(wrapper.text()).toContain("数据更新于 2026-10-27 13:41:21（北京时间）"); // the last answer, not a clock (issue 119)
    expect(serviceTime("2026-10-27T13:41:21")).toBe("2026-10-27 13:41:21");
    expect(positionNumber("p3")).toBe("3");
  });
});

describe("HistoryPage", () => {
  it("renders list, cards and detail from the store and keeps them on a failed query", async () => {
    const api = {
      health: vi.fn(async () => health()),
      snapshots: vi.fn(async () => snapshots()),
      devices: vi.fn(async () => devices(["p1"])),
      acquisitions: vi.fn(async () => page([item(2, "2026-10-18T08:00:00.000")])),
      acquisition: vi.fn(async (_key: string, id: number) => detail(id)),
      };
    const store = createHistoryStore(api as unknown as ApiClient);
    await store.init();
    const wrapper = mount(HistoryPage, { props: { store }, global: { stubs: { SpectrumChart: true } } });
    await flushPromises();
    expect(wrapper.findAll("tbody tr[data-id]")).toHaveLength(1);
    expect(wrapper.text()).toContain("记录详情 · 设备1 · #2");
    api.acquisitions.mockRejectedValueOnce(
      new ApiError(503, { code: "database_unavailable", message: "当前设备的数据库不可访问", retryable: true, detail: null }),
    );
    await wrapper.get("form.query").trigger("submit");
    await flushPromises();
    expect(wrapper.text()).toContain("当前设备的数据库不可访问");
    expect(wrapper.text()).toContain("仍显示上次查询结果");
    expect(wrapper.findAll("tbody tr[data-id]")).toHaveLength(1);
    expect(wrapper.text()).toContain("记录详情 · 设备1 · #2");
  });
});

function storeApi() {
  return {
    health: vi.fn(async () => health()),
    snapshots: vi.fn(async () => snapshots()),
    devices: vi.fn(async () => devices(["p1", "p2"])),
    acquisitions: vi.fn(async () => page([item(2, "2026-10-18T08:00:00.000")])),
    acquisition: vi.fn(async (_key: string, id: number) => detail(id)),
  };
}

describe("App global error (review M-2, N-5)", () => {
  it("重试 reloads health and lists without resetting the viewed device", async () => {
    const api = storeApi();
    const store = createHistoryStore(api as unknown as ApiClient);
    const dli = createDliStore(api as unknown as ApiClient);
    const calc = createCalcStore(api as unknown as ApiClient);
    const wrapper = mount(App, { props: { store, dli, calc, settings: createSettingsStore(api as unknown as ApiClient), overview: createOverviewStore(api as unknown as ApiClient) }, global: { stubs: { SpectrumChart: true } } });
    await flushPromises();
    await store.selectDevice("p2");
    api.devices.mockRejectedValueOnce(
      new ApiError(0, { code: "service_unavailable", message: "本机服务未响应", retryable: true, detail: null }),
    );
    await store.loadLists();
    await flushPromises();
    await wrapper.get(".global [data-code='service_unavailable'] button").trigger("click");
    await flushPromises();
    expect(store.state.devices.error).toBeNull();
    expect(store.state.deviceKey).toBe("p2");
    expect(wrapper.find(".global").exists()).toBe(false);
  });

  it("loads the charts' reference curves at start and again on a page change after a failure (API-08)", async () => {
    const api = storeApi();
    const reference = createReferenceStore({
      referenceCurves: vi
        .fn()
        .mockRejectedValueOnce(new ApiError(0, { code: "service_unavailable", message: "x", retryable: true, detail: null }))
        .mockResolvedValue(referenceCurves()),
    } as unknown as ApiClient);
    const store = createHistoryStore(api as unknown as ApiClient);
    const wrapper = mount(App, {
      props: {
        store,
        dli: createDliStore(api as unknown as ApiClient),
        calc: createCalcStore(api as unknown as ApiClient),
        settings: createSettingsStore(api as unknown as ApiClient),
        overview: createOverviewStore(api as unknown as ApiClient),
        reference,
      },
      global: { stubs: { SpectrumChart: true, DliPage: true, OverviewPage: true, CalcPage: true, SettingsPage: true } },
    });
    await flushPromises();
    expect(reference.state.data).toBeNull();
    await wrapper.findAll("nav button").at(-1)?.trigger("click");
    await flushPromises();
    expect(reference.state.data?.curves).toHaveLength(4);
    wrapper.unmount();
  });

  it("a failed device list does not claim that no snapshot was imported", async () => {
    const api = storeApi();
    api.devices.mockRejectedValue(
      new ApiError(0, { code: "service_unavailable", message: "本机服务未响应", retryable: true, detail: null }),
    );
    const store = createHistoryStore(api as unknown as ApiClient);
    await store.init();
    const wrapper = mount(HistoryPage, { props: { store }, global: { stubs: { SpectrumChart: true } } });
    expect(wrapper.text()).not.toContain("尚未导入历史库快照");
  });
});


describe("company brand (UI-093, as V1.0.3)", () => {
  it("the top bar shows the company logo, the product name and the trial notice with the build on hover", () => {
    const list = devices(["p1"]);
    const props = { devices: list.items, deviceKey: "p1", version: "2.0.0-alpha.9", run: runStatusView(null, null) };
    const wrapper = mount(TopBar, { props });
    const logo = wrapper.get("[data-role=brand-logo]");
    expect(logo.attributes("src")).toBeTruthy();
    expect(logo.attributes("alt")).toBe("PAR 光谱仪");
    expect(wrapper.get("[data-role=product-name]").text()).toBe("PAR 光谱仪专用软件");
    expect(wrapper.text()).toContain("ASMART-GROW-SPECTRA I");
    expect(wrapper.get("[data-role=product-version]").text()).toBe("V2.0 试用版");
    expect(wrapper.get("[data-role=product-version]").attributes("title")).toBe("V2.0 试用版 · 构建 9");
    // issue 119: no "alpha" in the brand's text or hover (the logo's URL is a file path, not shown)
    const brand = wrapper.get(".brand");
    const hovers = brand.findAll("[title]").map((node) => node.attributes("title") ?? "");
    expect([brand.text(), ...hovers].join(" ")).not.toContain("alpha");
  });

  it("关于与技术支持 lists the product and the support contact", () => {
    const wrapper = mount(AboutPanel, { props: { version: "2.0.0-alpha.9" } });
    const value = (label: string) => wrapper.get(`dd[data-label=${label}]`).text();
    expect(wrapper.get(".panel-title").text()).toBe("关于与技术支持");
    expect(wrapper.find("img").attributes("alt")).toBe("PAR 光谱仪");
    expect(value("软件名称")).toBe("PAR 光谱仪专用软件 ASMART-GROW-SPECTRA I");
    expect(value("软件版本")).toBe("V2.0 试用版 · 构建 9");
    expect(wrapper.text()).not.toContain("alpha");
    expect(buildLabel("2.1.0")).toBe("2.1.0"); // a release version is shown as it is
    expect(wrapper.text()).not.toMatch(/公司主体|官方网站|办公地址/);
    expect(value("技术支持")).toBe("请通过电子邮件联系");
    expect(value("电子邮箱")).toBe("jesse.sijia.liu@gmail.com");
    expect(wrapper.text()).toContain("© 2026 jesse.sijia.liu。保留所有权利。");
    expect(mount(AboutPanel, { props: { version: null } }).get("dd[data-label=软件版本]").text()).toBe("V2.0 试用版");
  });
});

describe("top bar device states (UI-259, PR #95 review)", () => {
  it("marks a disabled device 停用 and an unreadable database as a fault", () => {
    const list = devices(["p1", "p2", "p3"]);
    const [p1, p2] = list.items;
    if (p1) Object.assign(p1, { display_state: "disabled", enabled: false });
    if (p2) Object.assign(p2, { display_state: "fault" });
    const wrapper = mount(TopBar, { props: { devices: list.items, deviceKey: "p3", version: null, run: runStatusView(null, null) } });
    const states = wrapper.findAll("[data-role=device-state]").map((node) => node.text());
    expect(states).toEqual(["（停用）", "（库不可用）"]);
    expect(wrapper.get("button.device[data-key=p1]").attributes("title")).toContain("设备1（停用）");
    expect(wrapper.get("button.device[data-key=p1]").classes()).toContain("disabled");
  });
});
