import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { defineComponent, h, provide } from "vue";
import { ApiError, type ApiClient } from "../src/api/client";
import type { Spectrum } from "../src/api/types";
import OperationChart from "../src/components/OperationChart.vue";
import OverviewChart from "../src/components/OverviewChart.vue";
import SpectrumChart from "../src/components/SpectrumChart.vue";
import { fillSegments, matplotlibWidth, rgbHex } from "../src/lib/spectrum";
import { createReferenceStore, REFERENCE_CURVES, type ReferenceStore } from "../src/pages/referenceStore";
import { operationPage, overview, referenceCurves } from "./fixtures";

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

interface Series {
  type: string;
  name?: string;
  data: unknown[];
  yAxisIndex?: number;
  lineStyle?: { type?: unknown; width?: number; opacity?: number };
  areaStyle?: unknown;
  renderItem?: (params: unknown, api: unknown) => { children: { type: string; style: Record<string, unknown> }[] };
}
interface Option {
  series: Series[];
  yAxis: unknown;
  legend?: { data: string[]; selectedMode?: boolean };
}

const spectrum: Spectrum = {
  wavelength_start: 350,
  wavelength_step: 1,
  spectral_coefficient: 3,
  points: [1000, 2000, 3000],
  values: [1, 2, 3],
};

function loadedStore(): ReferenceStore {
  const store = createReferenceStore({ referenceCurves: async () => referenceCurves() } as unknown as ApiClient);
  store.state.data = referenceCurves();
  return store;
}

/** Mounts `child` under a parent that provides the reference store, as App does. */
function withReference(store: ReferenceStore | null, child: ReturnType<typeof defineComponent>, props: object) {
  const Host = defineComponent({
    setup() {
      if (store) provide(REFERENCE_CURVES, store);
      return () => h(child, props);
    },
  });
  charts.options.length = 0;
  return mount(Host);
}

const last = () => charts.options.at(-1) as unknown as Option;
const fill = (option: Option) => option.series.find((series) => series.type === "custom");
const curves = (option: Option) => option.series.filter((series) => series.yAxisIndex === 1);

describe("wavelength colours (UI-317)", () => {
  it("turns the service's 0–1 RGB into hex", () => {
    expect(rgbHex([1, 0, 0])).toBe("#ff0000");
    expect(rgbHex([0.55, 0.55, 0.55])).toBe("#8c8c8c");
    expect(rgbHex([0, 0.5, 1])).toBe("#0080ff");
  });

  it("gives segment i the colour of its left wavelength and skips gaps", () => {
    const reference = referenceCurves();
    expect(fillSegments([[350, 1], [351, 2], [352, 3]], reference)).toEqual([
      [350, 1, 351, 2, 0],
      [351, 2, 352, 3, 1],
    ]);
    expect(fillSegments([[350, 1], [351, null], [352, 3], [353, 4]], reference)).toEqual([[352, 3, 353, 4, 2]]);
  });
});

describe("matplotlib line widths", () => {
  it("draws a width in points at V1.0.3's 100 dpi", () => {
    expect(matplotlibWidth(0.72)).toBeCloseTo(1);
    expect(matplotlibWidth(1.6)).toBeCloseTo(2.222, 3);
  });
});

describe("reference store (API-08)", () => {
  it("loads once and keeps the curves", async () => {
    const api = { referenceCurves: vi.fn(async () => referenceCurves()) };
    const store = createReferenceStore(api as unknown as ApiClient);
    await store.load();
    await store.load();
    expect(api.referenceCurves).toHaveBeenCalledTimes(1);
    expect(store.state.data?.curves).toHaveLength(4);
  });

  it("tries again on the next load after a failure (R-1-5)", async () => {
    const api = {
      referenceCurves: vi
        .fn()
        .mockRejectedValueOnce(new ApiError(503, { code: "internal", message: "x", retryable: true, detail: null }))
        .mockResolvedValueOnce(referenceCurves()),
    };
    const store = createReferenceStore(api as unknown as ApiClient);
    await store.load();
    expect(store.state.data).toBeNull();
    await store.load();
    expect(api.referenceCurves).toHaveBeenCalledTimes(2);
    expect(store.state.data).not.toBeNull();
  });
});

describe("history spectrum chart (UI-168, UI-317)", () => {
  it("fills by wavelength and overlays the four curves on a right axis", () => {
    withReference(loadedStore(), SpectrumChart, { spectrum, caption: "" });
    const option = last();
    const segments = fill(option);
    expect(segments?.data).toEqual([
      [350, 1, 351, 2, 0],
      [351, 2, 352, 3, 1],
    ]);
    expect(curves(option).map((series) => series.name)).toEqual([
      "叶绿素 A",
      "叶绿素 B",
      "McCree 相对作用曲线（参考）",
      "人眼明视觉响应 V(λ，虚线)",
    ]);
    expect(curves(option).map((series) => series.lineStyle?.type)).toEqual([
      "dashed",
      "dotted",
      [6, 3, 1, 3],
      "dashed",
    ]);
    expect(option.legend?.data).toEqual(curves(option).map((series) => series.name));
    // fixed overlay (UI-168): a click on the legend does not hide a curve
    expect(option.legend?.selectedMode).toBe(false);
    // V1.0.3's matplotlib widths in points at its 100 dpi, as CSS pixels
    expect(curves(option).map((series) => series.lineStyle?.width)).toEqual(
      referenceCurves().curves.map((curve) => (curve.width * 100) / 72),
    );
    const right = (option.yAxis as { name: string; min: number; max: number; position: string }[])[1];
    expect(right).toMatchObject({ name: "归一化响应（叶绿素 / McCree）", min: 0, max: 1.5, position: "right" });
    // the plain line stays for the tooltip but is not drawn over the coloured segments
    const base = option.series.find((series) => series.type === "line" && series.yAxisIndex === undefined);
    expect(base?.lineStyle?.opacity).toBe(0);
    expect(base?.areaStyle).toBeUndefined();
  });

  it("draws each segment from the baseline in its colour at the service's opacity", () => {
    withReference(loadedStore(), SpectrumChart, { spectrum, caption: "" });
    const segments = fill(last());
    const api = {
      value: (index: number) => [350, 1, 351, 2, 1][index],
      coord: ([x = 0, y = 0]: number[]) => [x, -y],
    };
    const drawn = segments?.renderItem?.({}, api);
    const [area, line] = drawn?.children ?? [];
    expect(area?.type).toBe("polygon");
    expect(area?.style).toMatchObject({ fill: "#0000ff", opacity: 0.55 });
    expect(line?.type).toBe("line");
    expect(line?.style).toMatchObject({ stroke: "#0000ff" });
  });

  it("keeps the single-colour chart until the curves are loaded", () => {
    withReference(null, SpectrumChart, { spectrum, caption: "" });
    const option = last();
    expect(fill(option)).toBeUndefined();
    expect(curves(option)).toEqual([]);
    expect(option.series[0]?.areaStyle).toBeDefined();
  });

  it("redraws when the curves arrive", async () => {
    const store = createReferenceStore({ referenceCurves: async () => referenceCurves() } as unknown as ApiClient);
    withReference(store, SpectrumChart, { spectrum, caption: "" });
    expect(fill(last())).toBeUndefined();
    await store.load();
    await flushPromises();
    expect(fill(last())).toBeDefined();
    expect(curves(last())).toHaveLength(4);
  });
});

describe("overview spectrum chart (UI-168, UI-278, UI-317)", () => {
  it("fills by wavelength and overlays the four curves", () => {
    const data = overview();
    withReference(loadedStore(), OverviewChart, { chart: data.chart, texts: data.texts, metricsVisible: true });
    const option = last();
    expect(fill(option)?.data).toEqual([[350, 1, 351, 2, 0]]);
    expect(curves(option)).toHaveLength(4);
    expect((option.yAxis as { max: number }[])[0]?.max).toBe(2 / 0.618);
  });

  it("draws nothing without a spectrum", () => {
    const empty = overview("p1", null);
    withReference(loadedStore(), OverviewChart, { chart: empty.chart, texts: empty.texts, metricsVisible: true });
    expect(last().series).toEqual([]);
  });
});

describe("calculation charts (UI-317; no reference curves, as V1.0.3)", () => {
  const base = { title: "光谱 A", yRange: [0, 4], yLabel: "功率", xLabel: "波长", axis: operationPage().axis };

  it("fills A, B and a sum or difference by wavelength", () => {
    withReference(loadedStore(), OperationChart, { ...base, values: [1, 2, null, 3] });
    const option = last();
    expect(fill(option)?.data).toEqual([[350, 1, 351, 2, 0]]);
    expect(curves(option)).toEqual([]);
  });

  it("keeps a ratio a plain line without fill (UI-223)", () => {
    withReference(loadedStore(), OperationChart, { ...base, values: [1, 2], ratio: true, variant: "result" });
    expect(fill(last())).toBeUndefined();
  });
});

describe("overview metrics card beside the response axis", () => {
  it("moves left of the right axis only while the curves are drawn", () => {
    const data = overview();
    const props = { chart: data.chart, texts: data.texts, metricsVisible: true };
    expect(withReference(loadedStore(), OverviewChart, props).find("[data-role=overlay]").classes()).toContain("beside-axis");
    expect(withReference(null, OverviewChart, props).find("[data-role=overlay]").classes()).not.toContain("beside-axis");
  });
});
