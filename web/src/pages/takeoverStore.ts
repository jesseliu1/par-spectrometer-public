/**
 * Tier and takeover state shared by the status bar, the settings page and the overview (16_ sections 4-6; D-214).
 *
 * The service decides everything: the tier, the second confirmation (a hidden button is not one, 16_ 4.2), the
 * status-bar text and colour, whether a start is allowed (V1.0.3's lock), the configuration rules (V1.0.3's
 * DeviceHub.apply and its messages) and what an import may bring. This store only asks, shows the answers and keeps
 * the last valid data when a request fails (R-1-5).
 *
 * Events (API-17) are hints: after each one the store reads the state again (GET /tier, GET /acquisition/status);
 * after every (re)connection too, because there is no replay. While the stream is down the page keeps what it shows
 * and says so (16_ section 6).
 *
 * Confirmations: 0 → 1 has two layers (the notice, then a checkbox and "开启档位 1"); 1 → 0 and "停止采集" have one
 * (stopping can take up to one acquisition transaction, about 40 s). Their texts are the service's (GET /tier
 * `stop_text`, `down_text`; with a halt the stop text repeats it). Nothing here clears a halt: its banner only
 * closes (red line; 16_ section 6).
 *
 * An unusable configuration (D-220): GET /acquisition-config names the `problem` (also after a start refused with
 * config_unavailable). "以空配置重新配置…" asks once with the service's text (V1.0.3's startup question); confirmed,
 * the form becomes the service's empty configuration and the save says `reconfigure`, which the service accepts
 * without a takeover and backs the original file up first. A saved configuration that failed to apply in the
 * background is marked as not in effect from the status (`config_apply_error`, D-221); saving stays possible.
 *
 * 计算机串口 (#74): the computer's serial ports as V1.0.3's settings page lists them, read when the RTU fields are shown
 * and again on 刷新串口; a failed read keeps the last list (R-1-5). Picking one only fills the field, which stays
 * free text; nothing is chosen or switched automatically (POLL-032).
 *
 * An unexpected error of the service (D-225 item 1): GET /tier names the last one (`fault`) and a `service_error`
 * event announces it. The page shows the service's text in a banner until 知道了 (closing it changes nothing in the
 * service); after a takeover fault the tier read again is 0 and the takeover released.
 */
import { reactive } from "vue";
import type { ApiClient } from "../api/client";
import type {
  AcquisitionConfig,
  AcquisitionStatus,
  BusValues,
  ConfigRow,
  ImportPreview,
  SerialPorts,
  ServiceEvent,
  ServiceFault,
  TierConfirmation,
  TierState,
} from "../api/types";
import { createResource, reset, run, type Resource } from "../lib/resource";
import { connectEvents, type EventStream, type StreamState } from "../lib/sse";

export type TakeoverDialog = "none" | "notice" | "confirm" | "down" | "down1" | "stop" | "reconfigure";

export interface ConfigDraft {
  bus: BusValues;
  rows: ConfigRow[];
}

export interface TakeoverState {
  tier: Resource<TierState>;
  status: Resource<AcquisitionStatus>;
  config: Resource<AcquisitionConfig>;
  /** the form being edited; null until the configuration was read */
  draft: ConfigDraft | null;
  dirty: boolean;
  /** the form is the empty configuration of "以空配置重新配置" (D-220); the save asks to reconfigure */
  reconfiguring: boolean;
  saving: Resource<AcquisitionConfig>;
  /** V1.0.3's "配置已保存，等待当前事务结束后应用。" after a save, until the next edit */
  saved: boolean;
  importPath: string;
  importing: Resource<ImportPreview>;
  /** the computer's serial ports for 计算机串口 (V1.0.3's 刷新串口, #74) */
  serialPorts: Resource<SerialPorts>;
  dialog: TakeoverDialog;
  confirming: Resource<TierConfirmation>;
  /** second layer: "我已了解上述影响" */
  acknowledged: boolean;
  tierChange: Resource<TierState>;
  action: Resource<AcquisitionStatus>;
  stream: StreamState | "idle";
  /** acquisition_saved events seen (the overview reloads on a change) */
  savedRecords: number;
  lastSaved: { key: string; record_id: number } | null;
  /** occurred_at of the halt whose banner was closed with 确认 */
  haltSeen: string | null;
  /** id of the service fault whose banner was closed with 知道了 (D-225 item 1) */
  faultSeen: number | null;
}

export const STREAM_DOWN = "与本机服务的连接已断开，正在重连；页面保留最后的数据";

/** Events that change what GET /acquisition/status answers (16_ section 5). */
const STATUS_EVENTS = new Set([
  "bus_state",
  "bus_config",
  "config_applied", // read through loadTier, which reads the status after the tier (onEvent)
  "device_state",
  "device_alert",
  "acquisition_saved",
  "acquisition_halted",
  "maintenance_changed",
  "task_finished",
]);

export type TakeoverStore = ReturnType<typeof createTakeoverStore>;

function copyDraft(bus: BusValues, rows: ConfigRow[]): ConfigDraft {
  return { bus: { ...bus }, rows: rows.map((row) => ({ ...row })) };
}

export function createTakeoverStore(api: ApiClient, events: { connect: boolean } = { connect: true }) {
  const state: TakeoverState = reactive({
    tier: createResource<TierState>(),
    status: createResource<AcquisitionStatus>(),
    config: createResource<AcquisitionConfig>(),
    draft: null,
    dirty: false,
    reconfiguring: false,
    saving: createResource<AcquisitionConfig>(),
    saved: false,
    importPath: "",
    importing: createResource<ImportPreview>(),
    serialPorts: createResource<SerialPorts>(),
    dialog: "none",
    confirming: createResource<TierConfirmation>(),
    acknowledged: false,
    tierChange: createResource<TierState>(),
    action: createResource<AcquisitionStatus>(),
    stream: "idle",
    savedRecords: 0,
    lastSaved: null,
    haltSeen: null,
    faultSeen: null,
  }) as TakeoverState;
  let stream: EventStream | null = null;
  /** Other stores that follow the same event stream (the maintenance page, 17_ section 9). */
  const listeners = new Set<(event: ServiceEvent) => void>();

  function listen(listener: (event: ServiceEvent) => void): () => void {
    listeners.add(listener);
    return () => listeners.delete(listener);
  }

  /** The tier reads 0 (settings file unreadable or changed) while a takeover is not released: the service keeps
   * acquiring and still answers status and stop (D-215), so the pages keep the running state and 停止采集, and
   * offer neither 开始采集 nor saving (PR #54 review M2). */
  function heldOver(): boolean {
    const tier = state.tier.data;
    return tier !== null && tier.tier < 1 && tier.takeover !== "released";
  }

  /** The status can be read: tier 1, or a takeover not yet released whatever the tier reads. */
  function engaged(): boolean {
    return (state.tier.data?.tier ?? 0) >= 1 || heldOver();
  }

  async function loadStatus(): Promise<boolean> {
    if (!engaged()) {
      reset(state.status);
      return false;
    }
    const ok = await run(state.status, () => api.acquisitionStatus());
    state.status.retry = loadStatus;
    return ok;
  }

  /** GET /tier, then the status when tier 1 allows it or a takeover is still not released. */
  async function loadTier(): Promise<boolean> {
    const ok = await run(state.tier, () => api.tier());
    state.tier.retry = loadTier;
    if (ok) await loadStatus();
    return ok;
  }

  function onEvent(event: ServiceEvent): void {
    for (const listener of listeners) listener(event);
    // maintenance_changed: the status bar reads "档位 2 · 通信维护中" (17_ 6.1), which GET /tier answers
    // service_error: GET /tier names the fault; after a takeover fault the tier reads 0 (D-225 item 1)
    if (
      event.name === "tier_changed" ||
      event.name === "takeover_state" ||
      event.name === "maintenance_changed" ||
      event.name === "service_error"
    ) {
      void loadTier();
      return;
    }
    if (event.name === "acquisition_saved") {
      state.savedRecords += 1;
      state.lastSaved = { key: String(event.data.key ?? ""), record_id: Number(event.data.record_id ?? 0) };
    }
    if (event.name === "config_applied" && state.config.data !== null && !state.dirty) void loadConfig();
    // config_applied: the mode text reads "等待登记设备" until a configuration is saved, which GET /tier answers
    if (event.name === "config_applied") void loadTier();
    else if (STATUS_EVENTS.has(event.name)) void loadStatus();
  }

  function onStream(next: StreamState): void {
    state.stream = next;
    if (next === "open") void loadTier(); // no replay: read the state again after every (re)connection
  }

  async function init(): Promise<void> {
    if (events.connect && stream === null) {
      stream = connectEvents({ open: (signal) => api.openEvents(signal), onEvent, onState: onStream });
    }
    await loadTier();
  }

  function dispose(): void {
    stream?.close();
    stream = null;
  }

  // ------------------------------------------------------------------ tier
  /** 0 → 1 and 1 → 2: the service issues the confirmation and both texts; the first layer opens. Lowering (2 → 1,
   * 1 → 0, 2 → 0): one confirmation with the service's text. */
  async function askTier(target: number): Promise<boolean> {
    state.acknowledged = false;
    const current = state.tier.data?.tier ?? 0;
    if (target === 0) {
      state.dialog = "down";
      return true;
    }
    if (target === 1 && current === 2) {
      state.dialog = "down1";
      return true;
    }
    const ok = await run(state.confirming, () => api.confirmTier(target));
    state.confirming.retry = () => askTier(target);
    state.dialog = ok ? "notice" : "none";
    return ok;
  }

  function continueTier(): void {
    if (state.dialog === "notice") state.dialog = "confirm";
  }

  function setAcknowledged(value: boolean): void {
    state.acknowledged = value;
  }

  function cancelDialog(): void {
    state.dialog = "none";
    state.acknowledged = false;
    reset(state.confirming);
  }

  /** Second layer accepted: PUT /tier with the confirmation id (the service checks it; 409 when expired or used). */
  async function acceptTier(): Promise<boolean> {
    const issued = state.confirming.data;
    if (state.dialog !== "confirm" || !state.acknowledged || issued === null) return false;
    state.dialog = "none";
    state.acknowledged = false;
    reset(state.confirming);
    const ok = await run(state.tierChange, () => api.setTier(issued.tier, issued.confirmation_id));
    state.tierChange.retry = null; // a used or expired confirmation cannot be retried: ask again
    await loadTier();
    return ok;
  }

  async function confirmDown(): Promise<boolean> {
    if (state.dialog !== "down" && state.dialog !== "down1") return false;
    const target = state.dialog === "down1" ? 1 : 0;
    state.dialog = "none";
    const ok = await run(state.tierChange, () => api.setTier(target));
    state.tierChange.retry = async () => {
      state.dialog = target === 1 ? "down1" : "down";
      return confirmDown();
    };
    await loadTier();
    return ok;
  }

  // ------------------------------------------------------------ takeover
  async function start(): Promise<boolean> {
    if (heldOver()) return false; // the service refuses it too (tier 0)
    const ok = await run(state.action, () => api.startAcquisition());
    state.action.retry = start;
    if (ok && state.action.data !== null) state.status.data = state.action.data;
    // refused because the configuration cannot be used: read it again so the settings page shows the way out
    if (!ok && state.action.error?.code === "config_unavailable" && state.config.data !== null) await loadConfig();
    await loadTier();
    return ok;
  }

  function askStop(): void {
    state.dialog = "stop";
  }

  async function confirmStop(): Promise<boolean> {
    if (state.dialog !== "stop") return false;
    state.dialog = "none";
    const ok = await run(state.action, () => api.stopAcquisition());
    state.action.retry = async () => {
      state.dialog = "stop";
      return confirmStop();
    };
    await loadTier();
    return ok;
  }

  /** The red banner shows until 确认; it never clears the halt (no such control exists, red line). */
  function haltVisible(): boolean {
    const halt = state.status.data?.halt ?? null;
    return halt !== null && (halt.occurred_at ?? "") !== state.haltSeen;
  }

  function dismissHalt(): void {
    state.haltSeen = state.status.data?.halt?.occurred_at ?? "";
  }

  /** The service's last unexpected error, until its banner was closed (a newer one shows again). */
  function faultShown(): ServiceFault | null {
    const fault = state.tier.data?.fault ?? null;
    return fault !== null && fault.id !== state.faultSeen ? fault : null;
  }

  function dismissFault(): void {
    state.faultSeen = state.tier.data?.fault?.id ?? null;
  }

  // --------------------------------------------------------- configuration
  async function loadConfig(): Promise<boolean> {
    const ok = await run(state.config, () => api.acquisitionConfig());
    state.config.retry = loadConfig;
    const data = state.config.data;
    if (ok && data !== null && (!state.dirty || state.draft === null)) {
      state.draft = copyDraft(data.bus, data.rows);
      state.dirty = false;
    }
    return ok;
  }

  function edited(): void {
    state.dirty = true;
    state.saved = false;
  }

  function setBus<K extends keyof BusValues>(field: K, value: BusValues[K]): void {
    if (state.draft === null) return;
    state.draft.bus[field] = value;
    edited();
  }

  function setRow<K extends keyof ConfigRow>(index: number, field: K, value: ConfigRow[K]): void {
    const row = state.draft?.rows[index];
    if (row === undefined) return;
    row[field] = value;
    edited();
  }

  /** "以空配置重新配置…": only while the service names a problem and nothing is taken over. */
  function canReconfigure(): boolean {
    return state.config.data?.problem != null && state.tier.data?.takeover === "released" && !heldOver();
  }

  function askReconfigure(): void {
    if (canReconfigure()) state.dialog = "reconfigure";
  }

  /** Confirmed: the form becomes the service's empty configuration; nothing is saved yet. */
  function confirmReconfigure(): boolean {
    const data = state.config.data;
    if (state.dialog !== "reconfigure" || data === null || !canReconfigure()) return false;
    state.dialog = "none";
    state.draft = copyDraft(data.blank_bus, data.blank_rows);
    state.reconfiguring = true;
    edited();
    reset(state.saving);
    return true;
  }

  function resetDraft(): void {
    const data = state.config.data;
    if (data === null) return;
    state.draft = copyDraft(data.bus, data.rows);
    state.reconfiguring = false;
    state.dirty = false;
    state.saved = false;
    reset(state.saving);
  }

  /** 保存并应用全部配置: the four rows as they are; the service applies V1.0.3's form rules and checks. A refusal
   * (V1.0.3's own message) keeps the form as typed. */
  async function save(): Promise<boolean> {
    const draft = state.draft;
    if (draft === null || heldOver()) return false;
    const body = {
      bus: { ...draft.bus },
      devices: draft.rows.map((row) => ({
        name: row.name,
        slave_id: row.slave_id,
        enabled: row.enabled,
        auto_stop_on_failure: row.auto_stop_on_failure,
        database_path: row.database_path,
        reuse_existing: row.reuse_existing,
      })),
      reconfigure: state.reconfiguring,
    };
    const ok = await run(state.saving, () => api.saveAcquisitionConfig(body));
    state.saving.retry = save;
    const data = state.saving.data;
    if (ok && data !== null) {
      state.config.data = data;
      state.config.error = null;
      state.draft = copyDraft(data.bus, data.rows);
      state.dirty = false;
      state.saved = true;
      state.reconfiguring = false;
    }
    return ok;
  }

  /** V1.0.3's 刷新串口: list the computer's serial ports again; a failure keeps the last list (R-1-5). */
  async function loadSerialPorts(): Promise<boolean> {
    const ok = await run(state.serialPorts, () => api.serialPorts());
    state.serialPorts.retry = loadSerialPorts;
    return ok;
  }

  function setImportPath(value: string): void {
    state.importPath = value;
  }

  async function previewImport(): Promise<boolean> {
    const path = state.importPath;
    const ok = await run(state.importing, () => api.importPreview(path));
    state.importing.retry = previewImport;
    return ok;
  }

  /** Put the importable devices and the bus into the form; nothing is saved until 保存并应用全部配置. */
  function applyImport(): boolean {
    const preview = state.importing.data;
    if (preview === null || state.draft === null) return false;
    state.draft = copyDraft({ ...state.draft.bus, ...preview.bus }, preview.rows);
    edited();
    reset(state.importing);
    return true;
  }

  function closeImport(): void {
    reset(state.importing);
  }

  return {
    state,
    listen,
    init,
    dispose,
    loadTier,
    loadStatus,
    heldOver,
    onEvent,
    onStream,
    askTier,
    continueTier,
    setAcknowledged,
    cancelDialog,
    acceptTier,
    confirmDown,
    start,
    askStop,
    confirmStop,
    haltVisible,
    dismissHalt,
    faultShown,
    dismissFault,
    loadConfig,
    canReconfigure,
    askReconfigure,
    confirmReconfigure,
    setBus,
    setRow,
    resetDraft,
    save,
    loadSerialPorts,
    setImportPath,
    previewImport,
    applyImport,
    closeImport,
  };
}
