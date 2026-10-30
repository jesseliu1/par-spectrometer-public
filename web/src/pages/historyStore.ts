/**
 * State of the history playback page (docs/design/ui-v2-pages.md 2.2; API-03, API-05, API-06).
 *
 * Everything shown comes from the service; this store only decides what to ask and keeps the last valid answer
 * when a request fails (R-1-5). Behaviour follows V1.0.x where the spec says so:
 *   UI-049 default range when the page first opens (and when the viewed device is replaced, see reloadDevices);
 *   UI-047 the applied range is kept when switching device; UI-050 the end time never advances by itself;
 *   UI-048 at most the newest 500 records of the range, with the "缩小时间范围" hint;
 *   UI-046 / D-201 (decided A) no paging: only offset 0 is requested;
 *   UI-032 an empty result clears the detail; UI-037 the selected row, detail and spectrum stay in step;
 *   V1.0.x refresh_history: keep the selected record when it is still in the list, else the first successful one.
 * The devices are those of the alpha's own configuration (issue #82; tier 0 lists none): the list is read again when
 * the tier or the configuration changes (reloadDevices). Retries repeat the whole action and keep the user's context
 * (R-1-5): the page-wide retry only reloads health and the list once it has loaded, and never resets the viewed
 * device or the applied range (retryLoad, UI-047).
 */
import { reactive } from "vue";
import type { ApiClient } from "../api/client";
import { ApiError } from "../api/client";
import type { AcquisitionDetail, DeviceList, Health, HistoryPage } from "../api/types";
import { createResource, invalidate, reset, run, type Resource } from "../lib/resource";
import {
  defaultRange,
  EARLIEST_QUERY,
  LATEST_QUERY,
  RangeInputError,
  toQueryRange,
  type QueryRange,
  type RangeInput,
} from "../lib/timeRange";

export interface HistoryState {
  health: Resource<Health>;
  devices: Resource<DeviceList>;
  page: Resource<HistoryPage>;
  detail: Resource<AcquisitionDetail>;
  deviceKey: string | null;
  rangeInput: RangeInput;
  applied: QueryRange | null;
  /** the record the user picked; the detail may still show an older one while this one loads or fails */
  selectedId: number | null;
  inputError: string | null;
}

export type HistoryStore = ReturnType<typeof createHistoryStore>;

function firstConfigured(devices: DeviceList | null): string | null {
  return devices?.items.find((device) => device.configured)?.key ?? null;
}

export function createHistoryStore(api: ApiClient) {
  const state: HistoryState = reactive({
    health: createResource<Health>(),
    devices: createResource<DeviceList>(),
    page: createResource<HistoryPage>(),
    detail: createResource<AcquisitionDetail>(),
    deviceKey: null,
    rangeInput: { start: "", end: "" },
    applied: null,
    selectedId: null,
    inputError: null,
  }) as HistoryState;

  async function loadLists(): Promise<boolean> {
    return run(state.devices, () => api.devices());
  }

  /** UI-049: the default range from the newest 500 records of the device (or today when there are none). */
  async function applyDefaultRange(key: string | null): Promise<boolean> {
    let asOf = state.devices.data?.as_of ?? null;
    let oldest: string | null = null;
    if (key !== null) {
      const probe = createResource<HistoryPage>();
      const ok = await run(probe, () => api.acquisitions(key, { start: EARLIEST_QUERY, end: LATEST_QUERY }));
      if (state.deviceKey !== key) return false; // the user switched device meanwhile: leave that one alone
      if (!ok || probe.data === null) {
        state.page.error = probe.error;
        state.page.retry = () => applyDefaultRange(key).then((done) => done && query());
        return false;
      }
      asOf = probe.data.as_of;
      oldest = probe.data.items.at(-1)?.acquired_at ?? null;
    }
    if (asOf === null) return false;
    state.rangeInput = defaultRange(asOf, oldest);
    state.applied = toQueryRange(state.rangeInput);
    return true;
  }

  async function init(): Promise<void> {
    await run(state.health, () => api.health());
    await loadLists();
    state.deviceKey = firstConfigured(state.devices.data);
    if (await applyDefaultRange(state.deviceKey)) await refresh();
  }

  /**
   * The page-wide "重试" (health or device list failed). Before any device list has loaded it is the first load;
   * afterwards it reloads health and the lists only, keeping the viewed device, the applied range and the list.
   */
  async function retryLoad(): Promise<boolean> {
    if (state.devices.data === null) {
      await init();
    } else {
      await Promise.all([run(state.health, () => api.health()), loadLists()]);
    }
    return state.health.error === null && state.devices.error === null;
  }

  /** "查询": apply the edited range (only now, UI-049/UI-050) and load the list. */
  async function query(): Promise<boolean> {
    try {
      state.applied = toQueryRange(state.rangeInput);
      state.inputError = null;
    } catch (error) {
      if (error instanceof RangeInputError) {
        state.inputError = error.message;
        return false;
      }
      throw error;
    }
    return refresh();
  }

  function pick(page: HistoryPage, previous: number | null): number | null {
    const items = page.items;
    if (previous !== null && items.some((item) => item.id === previous)) return previous;
    return (items.find((item) => item.success) ?? items[0])?.id ?? null;
  }

  /** Reload the list for the applied range and current device, keeping the selection when possible. */
  async function refresh(): Promise<boolean> {
    const key = state.deviceKey;
    const range = state.applied;
    if (key === null || range === null) {
      reset(state.page);
      clearSelection();
      return false;
    }
    const ok = await run(state.page, () => api.acquisitions(key, range));
    state.page.retry = refresh;
    if (!ok || state.page.data === null) return false;
    const id = pick(state.page.data, state.selectedId); // selectedId always belongs to the current device
    if (id === null) {
      clearSelection(); // UI-032
      return true;
    }
    await select(id);
    return true;
  }

  function clearSelection(): void {
    state.selectedId = null;
    reset(state.detail);
  }

  async function select(id: number): Promise<boolean> {
    const key = state.deviceKey;
    if (key === null) return false;
    state.selectedId = id;
    if (state.detail.data?.record.id === id && state.detail.data.device.key === key && !state.detail.error) {
      invalidate(state.detail); // a load for another record may still be underway; its late answer must be dropped (M-1)
      return true;
    }
    return run(state.detail, () => api.acquisition(key, id), ["record_not_found"]);
  }

  /** Switching the viewed device keeps the applied range (UI-047) and changes nothing in the service. */
  async function selectDevice(key: string): Promise<boolean> {
    if (key === state.deviceKey) return true;
    state.deviceKey = key;
    clearSelection();
    reset(state.page);
    return refresh();
  }

  /**
   * The tier or the configuration changed (tier_changed, config_applied): read the device list again. The viewed
   * device stays while it is still registered with the same database (UI-047); otherwise the first registered one
   * is shown with its default range, or nothing when none is left (tier 0). A failed read keeps the last list.
   */
  async function reloadDevices(): Promise<boolean> {
    const before = state.devices.data?.items.find((item) => item.key === state.deviceKey) ?? null;
    if (!(await loadLists())) return false;
    const after = state.devices.data?.items.find((item) => item.key === state.deviceKey) ?? null;
    if (before !== null && after?.configured && after.snapshot_id === before.snapshot_id) return true;
    const key = firstConfigured(state.devices.data);
    state.deviceKey = key;
    clearSelection();
    reset(state.page);
    if (await applyDefaultRange(key)) await refresh();
    return true;
  }

  return { state, init, retryLoad, query, refresh, select, selectDevice, reloadDevices, loadLists };
}

export function isRetryable(error: ApiError | null): boolean {
  return error !== null && error.retryable;
}
