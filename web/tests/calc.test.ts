import { flushPromises, mount } from "@vue/test-utils";
import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError } from "../src/api/client";
import type { OperationCandidate, OperationKey, SourceRef } from "../src/api/types";
import App from "../src/App.vue";
import OperationChart from "../src/components/OperationChart.vue";
import CalcPage from "../src/pages/CalcPage.vue";
import { createCalcStore, options } from "../src/pages/calcStore";
import { createDliStore } from "../src/pages/dliStore";
import { createHistoryStore } from "../src/pages/historyStore";
import { createOverviewStore } from "../src/pages/overviewStore";
import { createSettingsStore } from "../src/pages/settingsStore";
import { chartPoints, ticksFor } from "../src/lib/operations";
import { searchFor, viewFrom } from "../src/lib/view";
import {
  AS_OF,
  candidate,
  candidates,
  computation,
  devices,
  health,
  jsonResponse,
  operationInputs,
  operationPage,
  operationSources,
  page,
  snapshots,
} from "./fixtures";

// happy-dom has no canvas: ECharts is replaced by a recorder of the options the chart components set
const charts = vi.hoisted(() => ({ options: [] as Record<string, unknown>[] }));
vi.mock("echarts/core", () => ({
  use: () => undefined,
  init: () => ({
    setOption: (option: Record<string, unknown>) => charts.options.push(option),
    resize: () => undefined,
    dispose: () => undefined,
  }),
}));

const unavailable = (path = "/alpha/p2.sqlite") =>
  new ApiError(503, { code: "database_unavailable", message: `数据库不可访问：${path}`, retryable: true, detail: null });

const snapshotChanged = () =>
  new ApiError(409, { code: "snapshot_changed", message: "该位置已导入新快照", retryable: true, detail: null });

const LISTS: Record<string, OperationCandidate[]> = {
  p1: [candidate(5, "2026-10-18T08:05:00.000"), candidate(4, "2026-10-18T08:00:00.000")],
  p2: [candidate(9, "2026-10-18T08:04:00.000"), candidate(8, "2026-10-18T07:00:00.000")],
  p3: [],
};

function calcApi() {
  return {
    operationPage: vi.fn(async () => operationPage()),
    operationSources: vi.fn(async () => operationSources(["p1", "p2", "p3"])),
    operationSpectra: vi.fn(async (key: string, keep: number | null = null) => {
      const items = [...(LISTS[key] ?? [])];
      if (keep !== null && !items.some((item) => item.id === keep)) items.push(candidate(keep, "2026-09-01T00:00:00.000"));
      return candidates(key, items);
    }),
    operationNearest: vi.fn(async (key: string, _at: string) => ({
      as_of: AS_OF,
      source: "snapshot" as const,
      key,
      snapshot_id: `${key}-snap`,
      match: LISTS[key]?.[0] ? { ...LISTS[key][0], time_difference_seconds: -60 } : null,
    })),
    operationInputs: vi.fn(async (a: SourceRef | null, b: SourceRef | null) => operationInputs(a, b)),
    operationCompute: vi.fn(async (a: SourceRef, b: SourceRef, operation: OperationKey) => computation(a, b, operation)),
    operationExport: vi.fn(async (_a: SourceRef, _b: SourceRef, _op: OperationKey, formats: string[]) => ({
      as_of: AS_OF,
      directory: "/alpha/exports/A5_add_B9_x",
      files: formats.map((kind) => `A5_add_B9.${kind}`),
      text: `已保存 ${formats.length} 个文件：\n/alpha/exports/A5_add_B9_x`,
    })),
  };
}

async function started(api = calcApi()) {
  const store = createCalcStore(api as unknown as ApiClient);
  await store.show();
  return { api, store };
}

describe("calculation client", () => {
  it("addresses the six endpoints", async () => {
    const fetchImpl = vi.fn(async () => jsonResponse(200, {}));
    const api = new ApiClient("t", fetchImpl);
    const ref = { source: "p1", id: 5, snapshot_id: "s" };
    await api.operationPage();
    await api.operationSources();
    await api.operationSpectra("p1");
    await api.operationSpectra("p2", 7);
    await api.operationNearest("p2", "2026-10-18T08:00:00+08:00");
    await api.operationInputs(ref, null);
    await api.operationCompute(ref, ref, "divide");
    await api.operationExport(ref, ref, "add", ["csv"]);
    const calls = fetchImpl.mock.calls.map((call) => call as unknown as [string, RequestInit]);
    expect(calls.map(([url]) => url)).toEqual([
      "/api/v0/operations/page",
      "/api/v0/operation-sources",
      "/api/v0/operation-sources/p1/spectra",
      "/api/v0/operation-sources/p2/spectra?keep=7",
      "/api/v0/operation-sources/p2/nearest?acquired_at=2026-10-18T08%3A00%3A00%2B08%3A00",
      "/api/v0/operations/inputs",
      "/api/v0/operations/compute",
      "/api/v0/operations/export",
    ]);
    expect(JSON.parse(String(calls[5]?.[1].body))).toEqual({ a: ref, b: null });
    expect(JSON.parse(String(calls[7]?.[1].body))).toEqual({ a: ref, b: ref, operation: "add", formats: ["csv"] });
  });
});

describe("calculation store: selection rules (V1.0.3 _operation_a_changed and friends)", () => {
  it("starts with A on the first source, B on the second, and matches B to A's time (UI-156, UI-201)", async () => {
    const { api, store } = await started();
    expect([store.state.a.source, store.state.b.source]).toEqual(["p1", "p2"]);
    expect(store.state.a.selected).toBe(5); // the newest record
    expect(api.operationNearest).toHaveBeenCalledWith("p2", "2026-10-18T08:05:00.000");
    expect(store.state.b.selected).toBe(9);
    expect(api.operationInputs).toHaveBeenLastCalledWith(
      { source: "p1", id: 5, snapshot_id: "p1-snap" },
      { source: "p2", id: 9, snapshot_id: "p2-snap" },
    );
    expect(store.canRun()).toBe(true);
  });

  it("two show() calls at once start the page once", async () => {
    const api = calcApi();
    const store = createCalcStore(api as unknown as ApiClient);
    await Promise.all([store.show(), store.show()]);
    expect(api.operationSources).toHaveBeenCalledTimes(1);
    expect(api.operationNearest).toHaveBeenCalledTimes(1);
  });

  it("lists an older nearest record after the 500 and clears B when nothing matches (UI-204, UI-207)", async () => {
    const api = calcApi();
    api.operationNearest.mockResolvedValueOnce({
      as_of: AS_OF,
      source: "snapshot",
      key: "p2",
      snapshot_id: "p2-snap",
      match: { ...candidate(2, "2026-01-01T00:00:00.000"), time_difference_seconds: 1 },
    });
    const { store } = await started(api);
    expect(options(store.state.b).map((item) => item.id)).toEqual([9, 8, 2]);
    api.operationNearest.mockResolvedValueOnce({ as_of: AS_OF, source: "snapshot", key: "p2", snapshot_id: "s", match: null });
    await store.setRecord("a", 4);
    expect(options(store.state.b)).toEqual([]);
    expect(store.state.b.selected).toBeNull();
    expect(store.canRun()).toBe(false);
  });

  it("rematches B when A changes, never touches A when B is picked by hand (UI-163, UI-202, UI-205)", async () => {
    const { api, store } = await started();
    await store.setRecord("b", 8);
    expect(api.operationNearest).toHaveBeenCalledTimes(1);
    expect(store.state.a.selected).toBe(5);
    expect(store.state.b.selected).toBe(8);
    await store.setRecord("a", 4);
    expect(api.operationNearest).toHaveBeenLastCalledWith("p2", "2026-10-18T08:00:00.000");
    expect(store.state.b.selected).toBe(9);
  });

  it("keeps the sides independent with the option off and matches at once when it is turned on (UI-161, UI-203)", async () => {
    const { api, store } = await started();
    await store.setAutoMatch(false);
    await store.setRecord("b", 8);
    await store.setRecord("a", 4);
    expect(api.operationNearest).toHaveBeenCalledTimes(1);
    expect(store.state.b.selected).toBe(8);
    await store.setAutoMatch(true);
    expect(api.operationNearest).toHaveBeenCalledTimes(2);
    expect(store.state.b.selected).toBe(9);
  });

  it("changing B's database matches in the new one; changing A's keeps B's database (UI-162, UI-201)", async () => {
    const { api, store } = await started();
    await store.setSource("b", "p1");
    expect(api.operationNearest).toHaveBeenLastCalledWith("p1", "2026-10-18T08:05:00.000");
    expect(store.state.b.source).toBe("p1");
    await store.setSource("a", "p2");
    expect(store.state.b.source).toBe("p1");
    expect(store.state.a.selected).toBe(9);
  });

  it("an empty database lists 无可用光谱 and blocks the calculation (UI-269)", async () => {
    const { store } = await started();
    await store.setSource("b", "p3");
    expect(options(store.state.b)).toEqual([]);
    expect(store.state.inputs.data?.valid).toBe(false);
    expect(store.canRun()).toBe(false);
  });

  it("a database that fails to load keeps the old source and list and offers a retry (R-1-5)", async () => {
    const { api, store } = await started();
    api.operationSpectra.mockRejectedValueOnce(unavailable());
    expect(await store.setSource("b", "p3")).toBe(false);
    expect(store.state.b.source).toBe("p2");
    expect(options(store.state.b).map((item) => item.id)).toEqual([9, 8]);
    expect(store.state.b.records.error?.code).toBe("database_unavailable");
    await store.state.b.records.retry?.();
    expect(store.state.b.source).toBe("p3");
  });

  it("swaps sources and records exactly without matching, and drops the result (UI-186, UI-187)", async () => {
    const { api, store } = await started();
    await store.calculate();
    expect(store.state.result).not.toBeNull();
    await store.swap();
    expect([store.state.a.source, store.state.a.selected, store.state.b.source, store.state.b.selected]).toEqual([
      "p2",
      9,
      "p1",
      5,
    ]);
    expect(api.operationNearest).toHaveBeenCalledTimes(1);
    expect(store.state.result).toBeNull();
    expect(options(store.state.a).map((item) => item.id)).toEqual([9, 8]);
  });

  it("any change of operation or input drops the result (UI-158, UI-164, UI-266)", async () => {
    const { store } = await started();
    await store.calculate();
    store.setOperation("divide");
    expect(store.state.result).toBeNull();
    await store.calculate();
    expect(store.state.result?.result.ratio).toBe(true);
    await store.setRecord("b", 8);
    expect(store.state.result).toBeNull();
  });

  it("a refresh keeps the selection and the result while the records still exist (UI-204, UI-267)", async () => {
    const { api, store } = await started();
    await store.setRecord("b", 8);
    await store.calculate();
    const calls = api.operationInputs.mock.calls.length;
    await store.show();
    expect(api.operationSpectra).toHaveBeenLastCalledWith("p2", 8);
    expect(store.state.b.selected).toBe(8);
    expect(store.state.result).not.toBeNull();
    expect(api.operationInputs.mock.calls.length).toBe(calls);
  });

  it("a re-imported source drops the result and redraws the inputs (D-208)", async () => {
    const { api, store } = await started();
    await store.calculate();
    api.operationSpectra.mockImplementation(async (key: string) => candidates(key, LISTS[key] ?? [], `${key}-new`));
    await store.show();
    expect(store.state.result).toBeNull();
    expect(api.operationInputs).toHaveBeenLastCalledWith(
      { source: "p1", id: 5, snapshot_id: "p1-new" },
      { source: "p2", id: 9, snapshot_id: "p2-new" },
    );
  });

  it("a 409 snapshot_changed on the A/B charts re-reads the sources and redraws on the new snapshots (D-208)", async () => {
    const { api, store } = await started();
    const sourcesBefore = api.operationSources.mock.calls.length;
    api.operationSpectra.mockImplementation(async (key: string) => candidates(key, LISTS[key] ?? [], `${key}-new`));
    api.operationInputs.mockRejectedValueOnce(snapshotChanged());
    expect(await store.setRecord("b", 8)).toBe(false);
    await flushPromises();
    expect(api.operationSources.mock.calls.length).toBe(sourcesBefore + 1);
    expect(store.state.result).toBeNull();
    expect(api.operationInputs).toHaveBeenLastCalledWith(
      { source: "p1", id: 5, snapshot_id: "p1-new" },
      { source: "p2", id: 8, snapshot_id: "p2-new" },
    );
    expect(store.canRun()).toBe(true);
  });

  it("a 409 snapshot_changed on 执行计算 drops the result, re-reads the sources and redraws (D-208)", async () => {
    const { api, store } = await started();
    await store.calculate();
    expect(store.state.result).not.toBeNull();
    store.setOperation("divide");
    const sourcesBefore = api.operationSources.mock.calls.length;
    api.operationSpectra.mockImplementation(async (key: string) => candidates(key, LISTS[key] ?? [], `${key}-new`));
    api.operationCompute.mockRejectedValueOnce(snapshotChanged());
    expect(await store.calculate()).toBe(false);
    await flushPromises();
    expect(api.operationSources.mock.calls.length).toBe(sourcesBefore + 1);
    expect(store.state.result).toBeNull();
    expect(api.operationInputs).toHaveBeenLastCalledWith(
      { source: "p1", id: 5, snapshot_id: "p1-new" },
      { source: "p2", id: 9, snapshot_id: "p2-new" },
    );
  });

  it("swap does nothing while 执行计算 is unavailable", async () => {
    const { api, store } = await started();
    api.operationInputs.mockRejectedValueOnce(unavailable());
    await store.setRecord("b", 8);
    const calls = api.operationInputs.mock.calls.length;
    expect(await store.swap()).toBe(false);
    expect([store.state.a.source, store.state.b.source]).toEqual(["p1", "p2"]);
    expect(api.operationInputs.mock.calls.length).toBe(calls);
  });

  it("a late nearest-match reply never overrides a newer choice of A", async () => {
    const { api, store } = await started();
    let release: () => void = () => undefined;
    const late = new Promise<void>((resolve) => {
      release = resolve;
    });
    api.operationNearest.mockImplementationOnce(async (key: string) => {
      await late;
      return { as_of: AS_OF, source: "snapshot", key, snapshot_id: `${key}-snap`, match: { ...candidate(8, "2026-10-18T07:00:00.000"), time_difference_seconds: 1 } };
    });
    const first = store.setRecord("a", 4);
    const second = store.setRecord("a", 5); // answered at once with record 9
    await second;
    release();
    await first;
    await flushPromises();
    expect(store.state.a.selected).toBe(5);
    expect(store.state.b.selected).toBe(9);
  });

  it("a late nearest-match reply never overrides B picked by hand meanwhile (UI-205; review #51 M-2)", async () => {
    const { api, store } = await started();
    let release: () => void = () => undefined;
    const late = new Promise<void>((resolve) => {
      release = resolve;
    });
    api.operationNearest.mockImplementationOnce(async (key: string) => {
      await late;
      return { as_of: AS_OF, source: "snapshot", key, snapshot_id: `${key}-snap`, match: { ...candidate(9, "2026-10-18T08:04:00.000"), time_difference_seconds: 1 } };
    });
    const changeA = store.setRecord("a", 4); // the match for A = 4 is still pending
    await store.setRecord("b", 8); // B picked by hand
    const inputsCalls = api.operationInputs.mock.calls.length;
    release();
    await changeA;
    await flushPromises();
    expect(store.state.b.selected).toBe(8);
    expect(api.operationInputs.mock.calls.length).toBe(inputsCalls); // the old match redraws nothing
    expect(api.operationInputs).toHaveBeenLastCalledWith(
      { source: "p1", id: 4, snapshot_id: "p1-snap" },
      { source: "p2", id: 8, snapshot_id: "p2-snap" },
    );
    expect(store.canRun()).toBe(true);
  });

  it("changing A drops the result at once, before the nearest match answers (UI-158, UI-266; review #51 M-3)", async () => {
    const { api, store } = await started();
    await store.calculate();
    expect(store.state.result).not.toBeNull();
    let release: () => void = () => undefined;
    const late = new Promise<void>((resolve) => {
      release = resolve;
    });
    api.operationNearest.mockImplementationOnce(async (key: string) => {
      await late;
      return { as_of: AS_OF, source: "snapshot", key, snapshot_id: `${key}-snap`, match: { ...LISTS.p2![0]!, time_difference_seconds: 1 } };
    });
    const changeA = store.setRecord("a", 4);
    expect(store.state.result).toBeNull(); // nothing left to export while the match is pending
    expect(store.canRun()).toBe(false);
    expect(await store.exportResult(["csv"])).toBe(false);
    expect(api.operationExport).not.toHaveBeenCalled();
    release();
    await changeA;
    await flushPromises();
    expect(store.state.result).toBeNull();
  });

  it("a calculation still pending when A changes never brings its result back (UI-266; review #51 M-3)", async () => {
    const { api, store } = await started();
    let releaseCompute: () => void = () => undefined;
    const slow = new Promise<void>((resolve) => {
      releaseCompute = resolve;
    });
    api.operationCompute.mockImplementationOnce(async (a: SourceRef, b: SourceRef, operation: OperationKey) => {
      await slow;
      return computation(a, b, operation);
    });
    let releaseMatch: () => void = () => undefined;
    const late = new Promise<void>((resolve) => {
      releaseMatch = resolve;
    });
    api.operationNearest.mockImplementationOnce(async (key: string) => {
      await late;
      return { as_of: AS_OF, source: "snapshot", key, snapshot_id: `${key}-snap`, match: { ...LISTS.p2![0]!, time_difference_seconds: 1 } };
    });
    const computing = store.calculate();
    const changeA = store.setRecord("a", 4);
    releaseCompute();
    expect(await computing).toBe(false);
    expect(store.state.result).toBeNull();
    releaseMatch();
    await changeA;
    await flushPromises();
    expect(store.state.result).toBeNull();
    expect(store.state.inputs.data?.a.id).toBe(4);
  });

  it("retrying a failed database change completes it: rematch, redraw and a usable 执行计算 (UI-266, R-1-5; review #51 M-1)", async () => {
    const { api, store } = await started();
    await store.calculate();
    expect(store.state.result).not.toBeNull();
    api.operationSpectra.mockRejectedValueOnce(unavailable());
    expect(await store.setSource("b", "p1")).toBe(false);
    expect(store.state.result).not.toBeNull(); // the failure keeps everything shown (R-1-5)
    expect(await store.state.b.records.retry?.()).toBe(true);
    expect(store.state.b.source).toBe("p1");
    expect(api.operationNearest).toHaveBeenLastCalledWith("p1", "2026-10-18T08:05:00.000");
    expect(store.state.b.selected).toBe(5);
    expect(store.state.result).toBeNull();
    expect(api.operationInputs).toHaveBeenLastCalledWith(
      { source: "p1", id: 5, snapshot_id: "p1-snap" },
      { source: "p1", id: 5, snapshot_id: "p1-snap" },
    );
    expect(store.inputsCurrent()).toBe(true);
    expect(store.canRun()).toBe(true);
  });

  it("retrying a database that failed on a refresh redraws like the refresh would (UI-204, R-1-5)", async () => {
    const { api, store } = await started();
    api.operationSpectra.mockImplementation(async (key: string) => {
      if (key === "p2") throw unavailable();
      return candidates(key, LISTS[key] ?? [], `${key}-new`);
    });
    await store.show();
    expect(store.state.b.records.error?.code).toBe("database_unavailable");
    api.operationSpectra.mockImplementation(async (key: string) => candidates(key, LISTS[key] ?? [], `${key}-new`));
    expect(await store.state.b.records.retry?.()).toBe(true);
    expect(api.operationInputs).toHaveBeenLastCalledWith(
      { source: "p1", id: 5, snapshot_id: "p1-new" },
      { source: "p2", id: 9, snapshot_id: "p2-new" },
    );
    expect(store.canRun()).toBe(true);
  });

  it("a failed redraw keeps the last charts, blocks 执行计算 and retries (R-1-5)", async () => {
    const { api, store } = await started();
    const shown = store.state.inputs.data;
    api.operationInputs.mockRejectedValueOnce(unavailable());
    await store.setRecord("b", 8);
    expect(store.state.inputs.data).toBe(shown);
    expect(store.state.inputs.error?.code).toBe("database_unavailable");
    expect(store.canRun()).toBe(false);
    await store.state.inputs.retry?.();
    expect(store.canRun()).toBe(true);
  });

  it("a failed calculation shows the error and keeps no stale result", async () => {
    const { api, store } = await started();
    api.operationCompute.mockRejectedValueOnce(unavailable());
    expect(await store.calculate()).toBe(false);
    expect(store.state.result).toBeNull();
    expect(store.state.compute.error?.retryable).toBe(true);
    expect(await store.calculate()).toBe(true);
  });

  it("exports the result on screen in the chosen formats (EXP-022, EXP-026)", async () => {
    const { api, store } = await started();
    expect(await store.exportResult(["csv"])).toBe(false); // nothing calculated yet: nothing to export
    await store.calculate();
    await store.exportResult(["csv", "xlsx"]);
    expect(api.operationExport).toHaveBeenCalledWith(
      { source: "p1", id: 5, snapshot_id: "p1-snap" },
      { source: "p2", id: 9, snapshot_id: "p2-snap" },
      "add",
      ["csv", "xlsx"],
    );
    expect(store.state.exporting.data?.files).toEqual(["A5_add_B9.csv", "A5_add_B9.xlsx"]);
  });

  it("a selection changed after 执行计算 leaves nothing to export (EXP-022)", async () => {
    const { api, store } = await started();
    await store.calculate();
    await store.setRecord("a", 4);
    expect(await store.exportResult(["csv"])).toBe(false);
    expect(api.operationExport).not.toHaveBeenCalled();
  });
});

describe("calculation page", () => {
  async function mounted(api = calcApi()) {
    const store = createCalcStore(api as unknown as ApiClient);
    charts.options.length = 0;
    const wrapper = mount(CalcPage, { props: { store }, attachTo: document.body });
    await store.show();
    await flushPromises();
    return { api, store, wrapper };
  }

  it("lays out the two control rows in the V1.0.3 order (UI-188) with the service's texts", async () => {
    const { wrapper } = await mounted();
    const rows = wrapper.findAll(".toolbar .row");
    expect(rows).toHaveLength(2);
    expect(rows[0]?.findAll("[data-testid]").map((node) => node.attributes("data-testid"))).toEqual([
      "a-source",
      "a-record",
      "swap",
      "b-source",
      "b-record",
    ]);
    expect(rows[1]?.findAll("[data-testid]").map((node) => node.attributes("data-testid"))).toEqual([
      "auto-match",
      "operation",
      "time-difference",
      "run",
      "export",
    ]);
    expect(wrapper.get("[data-testid=swap]").attributes("title")).toBe("交换光谱 A 与 B"); // UI-314
    expect(wrapper.get("[data-testid=time-difference]").text()).toBe("采集时间差：B 比 A 晚 60.000 秒");
    expect((wrapper.get("[data-testid=auto-match]").element as HTMLInputElement).checked).toBe(true);
    expect(wrapper.get("[data-testid=run]").attributes("disabled")).toBeUndefined();
    expect(wrapper.get("[data-testid=export]").attributes("disabled")).toBeDefined();
    expect(wrapper.get("[data-testid=a-source]").attributes("title")).toBe("源库：/v1/p1.sqlite3"); // UI-265
    wrapper.unmount();
  });

  it("shows the waiting result without y labels, then the ratio as a plain line with the 1× line", async () => {
    const { store, wrapper } = await mounted();
    expect(wrapper.get("[data-testid=chart-result-empty]").text()).toContain("等待执行计算"); // UI-210
    expect(wrapper.get("[data-testid=chart-result-title]").text()).toBe("计算结果"); // UI-213
    const waiting = wrapper.findAllComponents(OperationChart)[2];
    expect(waiting?.props("hideYLabels")).toBe(true); // UI-212
    await store.calculate(); // add: no 1× line
    await flushPromises();
    const added = charts.options.at(-1) as { series: Record<string, unknown>[] };
    expect(added.series[0]?.markLine).toBeUndefined();
    expect(charts.options.every((item) => (item as { series?: Record<string, unknown>[] }).series?.[0]?.markLine === undefined)).toBe(true);
    store.setOperation("divide");
    await store.calculate();
    await flushPromises();
    const option = charts.options.at(-1) as { series: Record<string, unknown>[]; yAxis: Record<string, unknown> };
    expect(option.series[0]?.areaStyle).toBeUndefined(); // UI-223
    expect(option.series[0]?.markLine).toBeDefined(); // UI-220
    expect(option.series[0]?.data).toEqual([
      [350, 0.5],
      [351, null],
      [352, null],
    ]); // UI-218: null stays a gap
    expect([option.yAxis.min, option.yAxis.max]).toEqual([0, 1.5]);
    expect(wrapper.get(".note").text()).toContain("2%");
    expect(wrapper.get("[data-testid=chart-result-title]").text()).toBe("计算结果：divide");
    wrapper.unmount();
  });

  it("lists 无可用光谱 for an empty database and disables its record list (UI-207, UI-269)", async () => {
    const { store, wrapper } = await mounted();
    await store.setSource("b", "p3");
    await flushPromises();
    const record = wrapper.get("[data-testid=b-record]");
    expect(record.text()).toBe("无可用光谱");
    expect(record.attributes("disabled")).toBeDefined();
    expect(wrapper.get("[data-testid=run]").attributes("disabled")).toBeDefined();
    expect(wrapper.get("[data-testid=chart-result-empty]").text()).toContain("缺少有效的 A/B 光谱"); // UI-216
    wrapper.unmount();
  });

  it("the guide shows bold inline headings and opens the full guide with chapters and outside links", async () => {
    const { wrapper } = await mounted();
    expect(wrapper.findAll("[data-testid=guide-summary] b").map((node) => node.text())).toEqual([
      "加法 A+B · 补光组合：",
      "比值 A/B · 叶片：",
    ]); // UI-226
    await wrapper.get(".guide button").trigger("click");
    const dialog = wrapper.get("[role=dialog]");
    expect(dialog.attributes("aria-label")).toBe("光谱计算应用说明"); // UI-229
    expect(dialog.attributes("style")).toContain("--dialog-width: 960px"); // UI-232: 960×760, at most 90 %
    expect(dialog.attributes("style")).toContain("--dialog-max-width: 90vw");
    expect(dialog.findAll(".chapters a").map((node) => node.text())).toEqual(["补光", "显示与导出"]); // UI-231
    const link = dialog.get(".links a");
    expect([link.attributes("target"), link.attributes("rel")]).toEqual(["_blank", "noopener noreferrer"]); // UI-230
    await dialog.get(".dialog-foot button").trigger("click");
    expect(wrapper.find("[role=dialog]").exists()).toBe(false);
    wrapper.unmount();
  });

  it("export dialog: CSV ticked, nothing chosen disables it, cancelling sends nothing (EXP-021, EXP-026)", async () => {
    const { api, store, wrapper } = await mounted();
    await store.calculate();
    await flushPromises();
    await wrapper.get("[data-testid=export]").trigger("click");
    const boxes = wrapper.findAll(".formats input");
    expect(boxes.map((box) => (box.element as HTMLInputElement).checked)).toEqual([true, false]);
    await boxes[0]?.setValue(false);
    expect(wrapper.get(".buttons .primary").attributes("disabled")).toBeDefined();
    await wrapper.findAll(".buttons button")[1]?.trigger("click");
    expect(wrapper.find(".formats").exists()).toBe(false);
    expect(api.operationExport).not.toHaveBeenCalled();
    await wrapper.get("[data-testid=export]").trigger("click");
    await wrapper.findAll(".formats input")[1]?.setValue(true);
    await wrapper.get(".buttons .primary").trigger("submit");
    await flushPromises();
    expect(api.operationExport).toHaveBeenCalledWith(expect.anything(), expect.anything(), "add", ["csv", "xlsx"]);
    expect(wrapper.get("[data-testid=export-done]").text()).toContain("已保存 2 个文件");
    wrapper.unmount();
  });

  it("an export failure names the folder and the files already written (EXP-020)", async () => {
    const api = calcApi();
    api.operationExport.mockRejectedValueOnce(
      new ApiError(500, {
        code: "export_failed",
        message: "导出失败",
        retryable: true,
        detail: "保存目录：/alpha/exports/x\n已完成：无\ndisk full",
      }),
    );
    const { store, wrapper } = await mounted(api);
    await store.calculate();
    await store.exportResult(["csv"]);
    await flushPromises();
    expect(wrapper.get("[data-testid=export-failed]").text()).toContain("保存目录：/alpha/exports/x");
    expect(store.state.result).not.toBeNull(); // the result stays on screen
    expect(wrapper.get("[data-testid=export]").attributes("disabled")).toBeUndefined(); // D-207: retry = export again
    expect(await store.exportResult(["csv"])).toBe(true);
    wrapper.unmount();
  });
});

describe("calculation helpers and navigation", () => {
  it("keeps null points and picks the tick set by width (UI-192, UI-218)", () => {
    expect(chartPoints([1, null], 350)).toEqual([
      [350, 1],
      [351, null],
    ]);
    const axis = operationPage().axis;
    expect(ticksFor(axis, 679)).toEqual(axis.ticks_narrow);
    expect(ticksFor(axis, 680)).toEqual(axis.ticks_wide);
    expect(ticksFor(axis, 0)).toEqual(axis.ticks_wide);
  });

  it("puts 光谱计算 between 历史回放 and 光积累计算 and opens it with ?view=calc (UI-167)", async () => {
    expect(viewFrom("?view=calc")).toBe("calc");
    expect(searchFor("", "calc")).toBe("?view=calc");
    const api = {
      health: vi.fn(async () => health()),
      snapshots: vi.fn(async () => snapshots()),
      devices: vi.fn(async () => devices(["p1", "p2"])),
      acquisitions: vi.fn(async () => page([])),
      acquisition: vi.fn(),
      importSnapshot: vi.fn(),
      dli: vi.fn(),
      ...calcApi(),
    };
    const client = api as unknown as ApiClient;
    const store = createHistoryStore(client);
    const calc = createCalcStore(client);
    const wrapper = mount(App, {
      props: { store, dli: createDliStore(client), calc, settings: createSettingsStore(client), overview: createOverviewStore(client), initialView: "calc" },
      global: { stubs: { SpectrumChart: true, OperationChart: true } },
    });
    await flushPromises();
    expect(wrapper.findAll("nav.tabs button .label").map((node) => node.text())).toEqual(["实时概览", "历史回放", "光谱计算", "光积累计算", "设置与导出"]);
    expect(wrapper.find("main.calc").exists()).toBe(true);
    expect([calc.state.a.source, calc.state.b.source]).toEqual(["p1", "p2"]);
    await store.selectDevice("p2"); // UI-159, UI-254: the top bar does not move A or B
    await flushPromises();
    expect([calc.state.a.source, calc.state.b.source]).toEqual(["p1", "p2"]);
    wrapper.unmount();
  });
});
