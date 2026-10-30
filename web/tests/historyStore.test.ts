import { describe, expect, it, vi } from "vitest";
import { ApiError, type ApiClient } from "../src/api/client";
import type { AcquisitionDetail, HistoryPage } from "../src/api/types";
import { createHistoryStore } from "../src/pages/historyStore";
import { EARLIEST_QUERY, LATEST_QUERY } from "../src/lib/timeRange";
import { detail, devices, health, item, page } from "./fixtures";

const unavailable = () =>
  new ApiError(503, { code: "database_unavailable", message: "当前设备的数据库不可访问", retryable: true, detail: null });

function fakeApi(overrides: Partial<Record<keyof ApiClient, unknown>> = {}) {
  const list = page([
    item(3, "2026-10-18T09:00:00.000", false),
    item(2, "2026-10-18T08:00:00.000"),
    item(1, "2026-10-17T07:00:00.000"),
  ]);
  const api = {
    health: vi.fn(async () => health()),
    devices: vi.fn(async () => devices(["p1", "p2"])),
    acquisitions: vi.fn(async (): Promise<HistoryPage> => list),
    acquisition: vi.fn(async (_key: string, id: number): Promise<AcquisitionDetail> => detail(id)),
  };
  Object.assign(api, overrides);
  return api;
}

function storeOf(api: ReturnType<typeof fakeApi>) {
  return createHistoryStore(api as unknown as ApiClient);
}

describe("history store", () => {
  it("opens with the UI-049 default range of the first registered device and selects the first success", async () => {
    const api = fakeApi();
    const store = storeOf(api);
    await store.init();
    expect(api.acquisitions).toHaveBeenNthCalledWith(1, "p1", { start: EARLIEST_QUERY, end: LATEST_QUERY });
    expect(store.state.rangeInput).toEqual({ start: "2026-10-17T00:00:00", end: "2026-10-18T09:30:15" });
    expect(api.acquisitions).toHaveBeenLastCalledWith("p1", {
      start: "2026-10-17T00:00:00.000",
      end: "2026-10-18T09:30:15.999",
    });
    expect(store.state.selectedId).toBe(2); // #3 failed: V1.0.x selects the first successful record
    expect(store.state.detail.data?.record.id).toBe(2);
  });

  it("without a registered device (tier 0) it queries nothing", async () => {
    const api = fakeApi({ devices: vi.fn(async () => devices([])) });
    const store = storeOf(api);
    await store.init();
    expect(store.state.deviceKey).toBeNull();
    expect(api.acquisitions).not.toHaveBeenCalled();
    expect(store.state.rangeInput.start).toBe("2026-10-18T00:00:00");
  });

  it("editing the range does nothing until 查询 (UI-049) and a bad value names the field", async () => {
    const api = fakeApi();
    const store = storeOf(api);
    await store.init();
    const calls = api.acquisitions.mock.calls.length;
    store.state.rangeInput = { start: "2026-10-18T08:00", end: "" };
    expect(api.acquisitions.mock.calls.length).toBe(calls);
    expect(await store.query()).toBe(false);
    expect(store.state.inputError).toBe("结束时间格式不正确");
    store.state.rangeInput = { start: "2026-10-18T08:00", end: "2026-10-18T09:00:00" };
    await store.query();
    expect(store.state.inputError).toBeNull();
    expect(api.acquisitions).toHaveBeenLastCalledWith("p1", {
      start: "2026-10-18T08:00:00.000",
      end: "2026-10-18T09:00:00.999",
    });
  });

  it("keeps the selected record when it is still in the new list", async () => {
    const api = fakeApi();
    const store = storeOf(api);
    await store.init();
    await store.select(1);
    await store.query();
    expect(store.state.selectedId).toBe(1);
  });

  it("keeps the last list and detail when the database becomes unavailable, then recovers on retry", async () => {
    const api = fakeApi();
    const store = storeOf(api);
    await store.init();
    const shown = store.state.page.data;
    api.acquisitions.mockRejectedValueOnce(unavailable());
    expect(await store.query()).toBe(false);
    expect(store.state.page.data).toBe(shown);
    expect(store.state.page.error?.code).toBe("database_unavailable");
    expect(store.state.detail.data?.record.id).toBe(2);
    expect(await store.state.page.retry?.()).toBe(true);
    expect(store.state.page.error).toBeNull();
  });

  it("keeps the shown detail when another record cannot be read", async () => {
    const api = fakeApi();
    const store = storeOf(api);
    await store.init();
    api.acquisition.mockRejectedValueOnce(unavailable());
    await store.select(1);
    expect(store.state.selectedId).toBe(1);
    expect(store.state.detail.data?.record.id).toBe(2);
    expect(store.state.detail.error?.retryable).toBe(true);
  });

  it("a late answer for another record never overwrites a selection served from cache (UI-037, review M-1)", async () => {
    const api = fakeApi();
    const store = storeOf(api);
    await store.init(); // record #2 is selected and its detail is loaded
    let releaseB: (value: AcquisitionDetail) => void = () => undefined;
    api.acquisition.mockImplementationOnce(() => new Promise<AcquisitionDetail>((resolve) => (releaseB = resolve)));
    const pendingB = store.select(1); // B: starts loading
    expect(await store.select(2)).toBe(true); // back to A: served from the cached detail
    releaseB(detail(1)); // B answers late
    expect(await pendingB).toBe(false);
    expect(store.state.selectedId).toBe(2);
    expect(store.state.detail.data?.record.id).toBe(2);
    expect(store.state.detail.loading).toBe(false);
  });

  it("empties the detail when the record no longer exists (UI-032)", async () => {
    const api = fakeApi();
    const store = storeOf(api);
    await store.init();
    api.acquisition.mockRejectedValueOnce(
      new ApiError(404, { code: "record_not_found", message: "记录 #1 不存在", retryable: false, detail: null }),
    );
    await store.select(1);
    expect(store.state.detail.data).toBeNull();
  });

  it("an empty result clears the selection and the detail (UI-032)", async () => {
    const api = fakeApi();
    const store = storeOf(api);
    await store.init();
    api.acquisitions.mockResolvedValueOnce(page([]));
    await store.query();
    expect(store.state.selectedId).toBeNull();
    expect(store.state.detail.data).toBeNull();
  });

  it("switching device keeps the applied range (UI-047) and clears the other device's selection", async () => {
    const api = fakeApi();
    const store = storeOf(api);
    await store.init();
    const applied = store.state.applied;
    await store.selectDevice("p2");
    expect(store.state.applied).toEqual(applied);
    expect(api.acquisitions).toHaveBeenLastCalledWith("p2", applied);
    expect(api.acquisition).toHaveBeenLastCalledWith("p2", 2);
  });

  it("a reloaded device list keeps the viewed device while its database is the same (UI-047)", async () => {
    const api = fakeApi();
    const store = storeOf(api);
    await store.init();
    await store.selectDevice("p2");
    const applied = store.state.applied;
    const queries = api.acquisitions.mock.calls.length;
    expect(await store.reloadDevices()).toBe(true);
    expect(store.state.deviceKey).toBe("p2");
    expect(store.state.applied).toEqual(applied);
    expect(api.acquisitions.mock.calls.length).toBe(queries);
  });

  it("a replaced or removed device opens the first registered one with its default range", async () => {
    const api = fakeApi();
    const store = storeOf(api);
    await store.init();
    await store.selectDevice("p2");
    api.devices.mockResolvedValueOnce(devices(["p1", "p2"], { p2: "p2-another" }));
    expect(await store.reloadDevices()).toBe(true);
    expect(store.state.deviceKey).toBe("p1");
    expect(api.acquisitions).toHaveBeenCalledWith("p1", { start: EARLIEST_QUERY, end: LATEST_QUERY });
    expect(store.state.selectedId).toBe(2);
  });

  it("tier 0 (no device left) empties the page and asks for nothing", async () => {
    const api = fakeApi();
    const store = storeOf(api);
    await store.init();
    api.devices.mockResolvedValueOnce(devices([]));
    const queries = api.acquisitions.mock.calls.length;
    expect(await store.reloadDevices()).toBe(true);
    expect(store.state.deviceKey).toBeNull();
    expect(store.state.page.data).toBeNull();
    expect(store.state.detail.data).toBeNull();
    expect(api.acquisitions.mock.calls.length).toBe(queries);
  });

  it("a failed reload keeps the list, the device and the shown records (R-1-5)", async () => {
    const api = fakeApi();
    const store = storeOf(api);
    await store.init();
    api.devices.mockRejectedValueOnce(unavailable());
    expect(await store.reloadDevices()).toBe(false);
    expect(store.state.deviceKey).toBe("p1");
    expect(store.state.devices.data?.items[0]?.configured).toBe(true);
    expect(store.state.page.data?.items).toHaveLength(3);
  });

  it("the global retry after the first load keeps the device and the applied range (review M-2)", async () => {
    const api = fakeApi();
    const store = storeOf(api);
    await store.init();
    await store.selectDevice("p2");
    store.state.rangeInput = { start: "2026-10-18T08:00", end: "2026-10-18T09:00" };
    await store.query();
    const applied = store.state.applied;
    api.devices.mockRejectedValueOnce(unavailable());
    await store.loadLists();
    expect(store.state.devices.error?.code).toBe("database_unavailable");
    const queries = api.acquisitions.mock.calls.length;
    expect(await store.retryLoad()).toBe(true);
    expect(store.state.devices.error).toBeNull();
    expect(store.state.deviceKey).toBe("p2");
    expect(store.state.applied).toEqual(applied);
    expect(store.state.rangeInput).toEqual({ start: "2026-10-18T08:00", end: "2026-10-18T09:00" });
    expect(api.acquisitions.mock.calls.length).toBe(queries);
  });

  it("the global retry before any device list was loaded runs the first load", async () => {
    const api = fakeApi();
    api.devices.mockRejectedValueOnce(unavailable());
    const store = storeOf(api);
    await store.init();
    expect(store.state.deviceKey).toBeNull();
    expect(await store.retryLoad()).toBe(true);
    expect(store.state.deviceKey).toBe("p1");
    expect(store.state.selectedId).toBe(2);
  });

  it("a new device's default range does not overwrite a device the user switched to meanwhile (review N-4)", async () => {
    const api = fakeApi({ devices: vi.fn(async () => devices(["p1", "p2", "p3"])) });
    const store = storeOf(api);
    await store.init();
    await store.selectDevice("p3");
    const applied = store.state.applied;
    let release: (value: HistoryPage) => void = () => undefined;
    api.acquisitions.mockImplementationOnce(() => new Promise<HistoryPage>((resolve) => (release = resolve)));
    api.devices.mockResolvedValueOnce(devices(["p1", "p2"]));
    const reloading = store.reloadDevices();
    await vi.waitFor(() => expect(api.acquisitions).toHaveBeenLastCalledWith("p1", expect.anything()));
    await store.selectDevice("p2");
    release(page([item(7, "2026-10-01T07:00:00.000")]));
    expect(await reloading).toBe(true);
    expect(store.state.deviceKey).toBe("p2");
    expect(store.state.applied).toEqual(applied);
    expect(api.acquisitions).toHaveBeenLastCalledWith("p2", applied);
  });
});
