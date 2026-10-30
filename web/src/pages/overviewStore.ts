/**
 * State of the overview page (实时概览; docs/design/ui-v2-pages.md 2.6; API-09; D-211; issue #82).
 *
 * The service builds every text (KPI cards, status line with the age, in-chart card, axis range) with the V1.0.3
 * rules; this store only decides what to ask and keeps the last valid answer of the viewed device when a request
 * fails (R-1-5). The viewed device is the top bar's (UI-040: switching changes nothing in the service). The page
 * reloads while shown (like the V1.0.3 3-second refresh), so "距今 N 秒" keeps moving.
 * "全部指标" (UI-009) loads the 54 values of the shown record through API-06; it is only possible while a record
 * is shown (UI-013). The loaded values belong to one (device, database, record): another device or another
 * database at the same position with the same record id is asked again, never shown from the cache (review of
 * PR #53, item 2). "显示指标" is checked at start and kept only for this page load (UI-061).
 *
 * Tier 1 (16_ section 5; D-213 q4; D-214): the page shows the alpha's own device databases through
 * GET /acquisition/devices/{key}/latest (`live`), for the live device chosen on the page. It reloads on every
 * acquisition_saved event and on the same 3-second timer; a failure keeps the last answer (R-1-5). "全部指标" of a
 * live record (issue 106, as V1.0.3) loads the same API-06 detail from the same database: the dialog keeps the title
 * and values of the record it was opened for while newer records arrive (V1.0.3's dialog is modal and fixed), and
 * another database at the position closes it. Tier 0 lists no device (issue #82), so the page is empty there.
 */
import { reactive } from "vue";
import type { ApiClient } from "../api/client";
import type { AcquisitionDetail, LiveOverview, Overview } from "../api/types";
import { createResource, invalidate, reset, run, type Resource } from "../lib/resource";

export interface OverviewState {
  overview: Resource<Overview>;
  details: Resource<AcquisitionDetail>;
  /** device whose overview is shown or loading */
  deviceKey: string | null;
  /** UI-061: in-chart metrics shown; true at start, not stored */
  metricsVisible: boolean;
  /** the record whose "全部指标" dialog is open, null when closed */
  detailsId: number | null;
  /** tier 1: the live overview of `liveKey` */
  live: Resource<LiveOverview>;
  liveKey: string | null;
  /** device, database and record the open (or last opened) dialog is for */
  detailsFor: DetailsTarget | null;
}

export interface DetailsTarget {
  key: string;
  snapshotId: string;
  id: number;
  /** "全部指标 · #ID · time" of the record when the dialog was opened (UI-009) */
  title: string;
}

function sameTarget(detail: AcquisitionDetail | null, target: DetailsTarget | null): boolean {
  return (
    detail !== null &&
    target !== null &&
    detail.device.key === target.key &&
    detail.snapshot_id === target.snapshotId &&
    detail.record.id === target.id
  );
}

export type OverviewStore = ReturnType<typeof createOverviewStore>;

export function createOverviewStore(api: ApiClient) {
  const state: OverviewState = reactive({
    overview: createResource<Overview>(),
    details: createResource<AcquisitionDetail>(),
    deviceKey: null,
    metricsVisible: true,
    detailsId: null,
    live: createResource<LiveOverview>(),
    liveKey: null,
    detailsFor: null,
  }) as OverviewState;

  /** Reload the live overview of the chosen live device; a failure keeps the shown one (R-1-5). */
  async function refreshLive(): Promise<boolean> {
    const key = state.liveKey;
    if (key === null) {
      reset(state.live);
      return false;
    }
    const ok = await run(state.live, () => api.liveOverview(key));
    state.live.retry = refreshLive;
    forgetIfReplaced(ok ? state.live.data : null);
    return ok;
  }

  /** Show live device `key` (a position of the alpha's configuration); another device's answer is never shown. */
  async function showLive(key: string | null): Promise<boolean> {
    if (key !== state.liveKey) {
      state.liveKey = key;
      reset(state.live);
      forgetDetails();
    }
    return refreshLive();
  }

  /** Reload the viewed device's overview; a failure keeps the shown one (R-1-5). */
  async function refresh(): Promise<boolean> {
    const key = state.deviceKey;
    if (key === null) {
      reset(state.overview);
      return false;
    }
    const ok = await run(state.overview, () => api.overview(key));
    state.overview.retry = refresh;
    forgetIfReplaced(ok ? state.overview.data : null);
    return ok;
  }

  /** Another database at the dialog's position: the open values may belong to another record #N. */
  function forgetIfReplaced(shown: Overview | LiveOverview | null): void {
    const target = state.detailsFor;
    if (shown !== null && target !== null && shown.device.key === target.key && shown.snapshot_id !== target.snapshotId) {
      forgetDetails();
    }
  }

  /** Show `key` (the top bar's device). Another device's overview is never shown as this one's. */
  async function showDevice(key: string | null): Promise<boolean> {
    if (key !== state.deviceKey) {
      state.deviceKey = key;
      reset(state.overview);
      forgetDetails();
    }
    return refresh();
  }

  /** UI-009: the 54 values of the record the page shows (the live one when `live`); disabled without one (UI-013). */
  async function openDetails(live = false): Promise<boolean> {
    const shown: Overview | LiveOverview | null = live ? state.live.data : state.overview.data;
    const key = live ? state.liveKey : state.deviceKey;
    if (shown === null || key === null || shown.device.key !== key || !shown.details_enabled) return false;
    const record = shown.display_record;
    if (record === null) return false;
    const target: DetailsTarget = { key, snapshotId: shown.snapshot_id, id: record.id, title: record.details_title };
    state.detailsId = record.id;
    state.detailsFor = target;
    if (sameTarget(state.details.data, target) && !state.details.error) {
      invalidate(state.details); // already loaded: a slower earlier load must not replace it
      return true;
    }
    return run(state.details, () => api.acquisition(key, record.id), ["record_not_found"]);
  }

  /** The loaded 54 values when they are those of the dialog's device, database and record; otherwise null. */
  function shownDetail(): AcquisitionDetail | null {
    return sameTarget(state.details.data, state.detailsFor) ? state.details.data : null;
  }

  /** Close the dialog and drop its values and pending loads (device switched or its database replaced). */
  function forgetDetails(): void {
    closeDetails();
    state.detailsFor = null;
    reset(state.details);
  }

  function closeDetails(): void {
    state.detailsId = null;
  }

  function setMetricsVisible(visible: boolean): void {
    state.metricsVisible = visible;
  }

  return { state, refresh, showDevice, openDetails, closeDetails, shownDetail, setMetricsVisible, refreshLive, showLive };
}
