/**
 * State of the DLI page (光积累计算; docs/design/ui-v2-pages.md 2.3; API-10).
 *
 * The service computes everything (period, totals, coverage, states, curve breaks) with the V1.0.3 code; this
 * store only decides what to ask and keeps the last valid answer of the viewed device when a request fails
 * (R-1-5). The viewed device is the one of the top bar (shared with the history page; switching changes nothing
 * in the service, UI-040). Without a date the current period is shown (= V1.0.3); a date picks the period in
 * progress at the end of that Beijing day (D-204 question 2, alpha only). The location inputs (issue 116) take the
 * device's saved location when a device is shown; typing changes nothing until 保存经纬度并重置周期 (DLI-025).
 */
import { reactive } from "vue";
import type { ApiClient } from "../api/client";
import type { DliDay } from "../api/types";
import { createResource, reset, run, type Resource } from "../lib/resource";

const DATE_INPUT = /^\d{4}-\d{2}-\d{2}$/;

export interface DliPageState {
  day: Resource<DliDay>;
  /** device whose period is shown or loading */
  deviceKey: string | null;
  /** null: the current period */
  appliedDate: string | null;
  dateInput: string;
  inputError: string | null;
  /** the location editors (V1.0.3's two spin boxes) and the device whose saved location they were filled from */
  latitudeInput: string | number;
  longitudeInput: string | number;
  locationKey: string | null;
  /** a location that cannot be sent (empty or not a number), shown beside the location editors */
  locationError: string | null;
  saving: Resource<DliDay>;
}

export type DliStore = ReturnType<typeof createDliStore>;

export function createDliStore(api: ApiClient) {
  const state: DliPageState = reactive({
    day: createResource<DliDay>(),
    deviceKey: null,
    appliedDate: null,
    dateInput: "",
    inputError: null,
    latitudeInput: "",
    longitudeInput: "",
    locationKey: null,
    locationError: null,
    saving: createResource<DliDay>(),
  }) as DliPageState;

  /** Fill the editors from the device's saved location, once per shown device (V1.0.3 bind_dli_location). */
  function syncLocation(force = false): void {
    const data = state.day.data;
    if (data === null || (!force && state.locationKey === data.device.key)) return;
    state.latitudeInput = data.location.latitude.toFixed(4);
    state.longitudeInput = data.location.longitude.toFixed(4);
    state.locationKey = data.device.key;
  }

  /** what the picker held after the last sync; only an input still equal to it is "untouched" (review N-2) */
  let syncedInput = "";

  /** Reload the applied period of the viewed device; a failure keeps the shown period (R-1-5). With `sync` (an
   * explicit 查看 / 当前周期) the answer's period date goes into the picker; a background reload only keeps an
   * untouched picker in step and never overwrites what the user is typing (review N-2). */
  async function refresh(sync = false): Promise<boolean> {
    const key = state.deviceKey;
    if (key === null) {
      reset(state.day);
      return false;
    }
    const date = state.appliedDate;
    const ok = await run(state.day, () => api.dli(key, date));
    state.day.retry = refresh;
    if (ok) syncLocation();
    if (ok && state.day.data !== null && (sync || state.dateInput === syncedInput)) {
      state.dateInput = state.day.data.period.date;
      syncedInput = state.dateInput;
    }
    return ok;
  }

  /** Show `key` (the top bar's device). Another device's period is never shown as this one's. */
  async function showDevice(key: string | null): Promise<boolean> {
    if (key !== state.deviceKey) {
      state.deviceKey = key;
      state.locationKey = null;
      reset(state.day);
      reset(state.saving);
    }
    return refresh();
  }

  /** "查看": the period of the picked date (only now, like the history query). */
  async function applyDate(): Promise<boolean> {
    const value = state.dateInput.trim();
    if (!DATE_INPUT.test(value)) {
      state.inputError = "请选择日期（年-月-日，北京时间）";
      return false;
    }
    state.inputError = null;
    state.appliedDate = value;
    return refresh(true);
  }

  /** "当前周期": back to the period in progress now (= V1.0.3). */
  async function showCurrent(): Promise<boolean> {
    state.inputError = null;
    state.appliedDate = null;
    return refresh(true);
  }

  /** 保存经纬度并重置周期 (issue 116): only now does the location apply; the answer is the shown period again,
   * computed from the new place. A refusal keeps the editors as typed and the period as shown (R-1-5). */
  async function saveLocation(): Promise<boolean> {
    const key = state.deviceKey;
    if (key === null) return false;
    // v-model on a number input may hand back a number; the editors are read as text either way
    const texts = [String(state.latitudeInput).trim(), String(state.longitudeInput).trim()];
    const [latitude, longitude] = texts.map(Number) as [number, number];
    if (texts.includes("") || !Number.isFinite(latitude) || !Number.isFinite(longitude)) {
      state.locationError = "请填写纬度和经度（数字，北纬、东经为正）";
      return false;
    }
    state.locationError = null;
    const ok = await run(state.saving, () => api.saveDliLocation(key, latitude, longitude, state.appliedDate));
    state.saving.retry = saveLocation;
    const saved = state.saving.data;
    if (ok && saved !== null && state.deviceKey === key) {
      // through run(): a reload still under way (read before the save) is dropped and the old error goes
      await run(state.day, async () => saved);
      state.day.retry = refresh;
      syncLocation(true);
    }
    return ok;
  }

  return { state, refresh, showDevice, applyDate, showCurrent, saveLocation };
}
