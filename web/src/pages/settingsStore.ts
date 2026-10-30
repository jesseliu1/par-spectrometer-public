/**
 * State of the settings page (设置与导出, alpha read-only; docs/design/ui-v2-pages.md 2.5; API-15, API-22, API-23,
 * API-26).
 *
 * The configuration is read only in tier 0 (D-209), where no device is listed (issue #82). The export section
 * follows the V1.0.3 page (MainWindow.update_export_range, _current_export_range, refresh_export_count,
 * export_acquisitions); the service computes every range, count, confirmation and file:
 *   * the export device is chosen on its own: on the first visit it is the viewed device of the top bar, later it
 *     stays what was chosen (EXP-041, EXP-042); only imported positions are listed (EXP-047);
 *   * a preset is recomputed by the service clock at each count, and the disabled editors show the window it
 *     returned (EXP-051, EXP-071); 自定义时间 keeps the last shown window and makes it editable (EXP-050); a
 *     custom range survives a change of export device (EXP-069) and is counted on the new database (EXP-070);
 *   * 导出采集记录 asks the service for the count at that moment, shows V1.0.3's notice or its one confirmation
 *     (EXP-053, EXP-059), and on 是 exports exactly the confirmed range of the confirmed database (EXP-052);
 *   * a failed request keeps what is shown and offers a retry (R-1-5); a failed export stays on the page and
 *     exporting again is the retry (as D-207).
 * The status area follows the viewed device (UI-080). In tier 1 it also shows V1.0.3's status line and device log
 * (API-16, GitHub issue 107); the page's 3-second timer re-reads the status area as V1.0.3's refresh_settings_console
 * does, each part keeping what it showed when a read fails (R-1-5).
 */
import { reactive } from "vue";
import type { ApiClient } from "../api/client";
import type {
  AcquisitionExported,
  DeviceLog,
  DeviceSummary,
  ExportCount,
  ExportCountQuery,
  ExportKind,
  SettingsDevice,
  SettingsView,
} from "../api/types";
import { createResource, reset, run, type Resource } from "../lib/resource";

const CUSTOM = "custom";
const KINDS: ExportKind[] = ["csv", "xlsx"];
const WHOLE_SECONDS = /^(\d{4}-\d{2}-\d{2})[T ](\d{2}:\d{2})(:\d{2})?(?:\.\d+)?$/;
export const EMPTY_TIME = "请按“年-月-日 时:分:秒”（如 2026-10-27 08:00:00）填写开始时间和结束时间（北京时间）";

export interface SettingsPageState {
  view: Resource<SettingsView>;
  summary: Resource<DeviceSummary>;
  /** status line and device log of the status area (API-16) */
  logs: Resource<DeviceLog>;
  /** device the status area shows (the top bar's) */
  summaryKey: string | null;
  /** export device; null until the first visit, then kept */
  exportKey: string | null;
  visited: boolean;
  range: string;
  /** the start/end editors, shown as V1.0.3 shows them (yyyy-MM-dd HH:mm:ss): the service's window for a preset,
   * the user's for custom */
  startInput: string;
  endInput: string;
  formats: Record<ExportKind, boolean>;
  count: Resource<ExportCount>;
  inputError: string | null;
  /** the custom range last taken from the editors (whole seconds); the refresh timer counts this one and never
   * reads or rewrites the editors while the user types */
  applied: { start: string; end: string } | null;
  /** the count whose confirmation is open */
  pending: ExportCount | null;
  /** V1.0.3's message instead of a confirmation (结束时间不能早于开始时间。 / 所选时间范围内没有采集记录。) */
  notice: string | null;
  exporting: Resource<AcquisitionExported>;
}

export type SettingsStore = ReturnType<typeof createSettingsStore>;

/** The positions that can be exported: the registered devices, in position order (EXP-044, EXP-047). */
export function exportDevices(state: SettingsPageState): SettingsDevice[] {
  return state.view.data?.devices.filter((item) => item.configured) ?? [];
}

export function chosenFormats(state: SettingsPageState): ExportKind[] {
  return KINDS.filter((kind) => state.formats[kind]);
}

/** An editor value ("YYYY-MM-DD HH:MM:SS" as V1.0.3 shows it; "T" or a missing ":SS" accepted) as the
 * service's whole-second form YYYY-MM-DDTHH:MM:SS, null when not a time. */
export function normaliseTime(value: string): string | null {
  const match = WHOLE_SECONDS.exec(value.trim());
  if (!match) return null;
  return `${match[1]}T${match[2]}${match[3] ?? ":00"}`;
}

export function createSettingsStore(api: ApiClient) {
  const state: SettingsPageState = reactive({
    view: createResource<SettingsView>(),
    summary: createResource<DeviceSummary>(),
    logs: createResource<DeviceLog>(),
    summaryKey: null,
    exportKey: null,
    visited: false,
    range: "1h",
    startInput: "",
    endInput: "",
    formats: { csv: true, xlsx: false },
    count: createResource<ExportCount>(),
    inputError: null,
    applied: null,
    pending: null,
    notice: null,
    exporting: createResource<AcquisitionExported>(),
  }) as SettingsPageState;

  /** The count query. A user action reads (and normalises) the editors; the refresh timer (`fromTimer`) uses the
   * last applied custom range and leaves the editors and their error line alone (review of PR #52). */
  function query(fromTimer = false): ExportCountQuery | null {
    const formats = chosenFormats(state);
    if (state.range !== CUSTOM) return { range: state.range, formats };
    if (fromTimer) return state.applied === null ? null : { range: CUSTOM, ...state.applied, formats };
    const start = normaliseTime(state.startInput);
    const end = normaliseTime(state.endInput);
    if (start === null || end === null) {
      state.inputError = EMPTY_TIME;
      return null;
    }
    state.inputError = null;
    state.startInput = start.replace("T", " ");
    state.endInput = end.replace("T", " ");
    state.applied = { start, end };
    return { range: CUSTOM, start, end, formats };
  }

  /** The preset's window as the service computed it goes into the (disabled) editors. */
  function showRange(data: ExportCount): void {
    if (data.range.mode !== CUSTOM) {
      state.startInput = data.range.start_text;
      state.endInput = data.range.end_text;
    }
  }

  /** refresh_export_count: the count of the export device for the current range and formats. */
  async function refreshCount(fromTimer = false): Promise<boolean> {
    const key = state.exportKey;
    if (key === null) {
      reset(state.count);
      return false;
    }
    const asked = query(fromTimer);
    if (asked === null) return false;
    const ok = await run(state.count, () => api.exportCount(key, asked));
    state.count.retry = () => refreshCount();
    if (ok && state.count.data !== null) showRange(state.count.data);
    return ok;
  }

  /** The export device after (re)reading the view: the first visit takes the viewed device (EXP-042); a device
   * that is no longer listed falls back to the first one (EXP-067). */
  function chooseExportDevice(viewed: string | null): void {
    const listed = exportDevices(state).map((item) => item.key);
    if (!state.visited) {
      state.visited = true;
      state.exportKey = viewed !== null && listed.includes(viewed) ? viewed : (listed[0] ?? null);
      return;
    }
    if (state.exportKey === null || !listed.includes(state.exportKey)) state.exportKey = listed[0] ?? null;
  }

  /** The status area of `key`: the database summary and, in tier 1, the status line and device log. Each keeps
   * its own error and retry. */
  async function loadSummary(key: string | null): Promise<boolean> {
    if (key !== state.summaryKey) {
      state.summaryKey = key;
      reset(state.summary);
      reset(state.logs);
    }
    if (key === null || !exportDevices(state).some((item) => item.key === key)) {
      reset(state.summary);
      reset(state.logs);
      return false;
    }
    const [summaryOk, logsOk] = await Promise.all([
      run(state.summary, () => api.deviceSummary(key)),
      run(state.logs, () => api.deviceLogs(key)),
    ]);
    state.summary.retry = () => loadSummary(key);
    state.logs.retry = () => loadSummary(key);
    return summaryOk && logsOk;
  }

  /** The top bar's device as last passed to show(); a retry restores the page for this one. */
  let viewedKey: string | null = null;
  let showGeneration = 0;

  /** Read the view; its retry finishes the whole page, not only the view (R-1-5; review #52 item 8). */
  async function loadView(): Promise<boolean> {
    const ok = await run(state.view, () => api.settings());
    state.view.retry = () => show(viewedKey);
    return ok;
  }

  /** The page is shown (or the device list changed, or the viewed device changed). Only the latest call goes on
   * after the view answers: an older one answering last never takes the status area or the export device back to
   * its device (review #52 item 7). Without any view yet (a failed first load) nothing is chosen, so the retry
   * still treats the page as a first visit (EXP-042). Resolves true when the view loaded and the page was
   * completed for this call. */
  async function show(viewed: string | null): Promise<boolean> {
    const generation = ++showGeneration;
    viewedKey = viewed;
    const loaded = await loadView();
    if (generation !== showGeneration || state.view.data === null) return false;
    chooseExportDevice(viewed);
    await Promise.all([loadSummary(viewed), refreshCount()]); // each keeps its own error and retry
    return loaded && generation === showGeneration;
  }

  /** The page's 3-second refresh (EXP-051): a preset moves on; a custom range is recounted as last applied; the
   * status area is read again (V1.0.3 refresh_settings_console). */
  async function tick(): Promise<boolean> {
    const [counted] = await Promise.all([refreshCount(true), loadSummary(state.summaryKey)]);
    return counted;
  }

  async function selectExportDevice(key: string): Promise<boolean> {
    state.exportKey = key;
    return refreshCount();
  }

  async function setRange(mode: string): Promise<boolean> {
    state.range = mode;
    state.inputError = null;
    return refreshCount();
  }

  async function applyCustom(): Promise<boolean> {
    return refreshCount();
  }

  async function setFormat(kind: ExportKind, on: boolean): Promise<boolean> {
    state.formats[kind] = on;
    return refreshCount();
  }

  /** 导出采集记录: the range at this moment (EXP-051), then V1.0.3's notice or its confirmation. */
  async function requestExport(): Promise<boolean> {
    state.notice = null;
    if (!(await refreshCount()) || state.count.data === null) return false;
    const fresh = state.count.data;
    if (fresh.notice !== null) {
      state.notice = fresh.notice;
      return false;
    }
    if (fresh.confirm === null) return false;
    state.pending = fresh;
    return true;
  }

  function cancelExport(): void {
    state.pending = null;
  }

  /** 是: export exactly what was confirmed (EXP-052). */
  async function confirmExport(): Promise<boolean> {
    const confirmed = state.pending;
    state.pending = null;
    if (confirmed === null) return false;
    const key = confirmed.device.key;
    const body = {
      start: confirmed.range.start,
      end: confirmed.range.end,
      formats: confirmed.formats,
      snapshot_id: confirmed.snapshot_id,
      ...(confirmed.confirm ? { records: confirmed.confirm.records } : {}),
    };
    const ok = await run(state.exporting, () => api.exportAcquisitions(key, body));
    state.exporting.retry = null; // exporting again goes through a new confirmation
    if (!ok && state.exporting.error?.code === "snapshot_changed") {
      await loadView();
      chooseExportDevice(state.summaryKey);
    }
    if (!ok) state.exporting.data = null;
    await refreshCount();
    return ok;
  }

  return {
    state,
    show,
    refreshCount,
    tick,
    selectExportDevice,
    setRange,
    applyCustom,
    setFormat,
    requestExport,
    cancelExport,
    confirmExport,
  };
}
