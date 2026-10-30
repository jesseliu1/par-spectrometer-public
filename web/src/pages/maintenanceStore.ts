/**
 * Tier 2 "设备维护" page state (内部文档; D-216).
 *
 * The service decides everything: V1.0.3's window conditions, which buttons are enabled and why not, every text, the
 * calibration values (it rounds an edit as V1.0.3's box does) and the verification state. This store asks, shows the
 * answer and keeps the last valid view when a request fails (R-1-5). A write is two requests: the service first
 * answers V1.0.3's dialog text with a one-time confirmation id (17_ 6.2), the page shows it with 是 / 否 (否 is the
 * default), and only 是 sends the write with that id. Nothing here can clear a hardware latch.
 *
 * Events (`maintenance_state`, `maintenance_changed`, `task_finished`, `acquisition_halted`, `takeover_state`) are
 * hints: the store reads GET /maintenance/state again after each one.
 */
import { reactive } from "vue";
import type { ApiClient } from "../api/client";
import type {
  CommFields,
  CommForm,
  DraftEdit,
  MaintenanceState,
  ServiceEvent,
  SettingsComm,
  WriteConfirmation,
} from "../api/types";
import { createResource, reset, run, type Resource } from "../lib/resource";

export interface PendingWrite {
  /** the write path under /maintenance (e.g. "comm/write"); the confirmation is `${path}/confirmations` */
  path: string;
  /** where the confirmed request goes: POST path (default) or DELETE /maintenance/page */
  send: "post" | "close";
  body: Record<string, unknown>;
  confirmation: WriteConfirmation;
}

export interface MaintenanceStoreState {
  view: Resource<MaintenanceState>;
  /** the last action: its error stays shown with 重试 until the next action (D-158) */
  action: Resource<MaintenanceState>;
  confirming: Resource<WriteConfirmation>;
  pending: PendingWrite | null;
  /** the communication tab's fields as typed (the service checks them) */
  form: CommForm;
  /** the target whose defaults the form was started from */
  formSource: string | null;
  /** 仅显示非零项 (a display filter of the diagnostics table, V1.0.3 default on) */
  nonZero: boolean;
  /** the event whose 事件详情 is open */
  details: string | null;
  settings: Resource<SettingsComm>;
}

const REFRESH_EVENTS = new Set([
  "maintenance_state",
  "maintenance_changed",
  "task_finished",
  "acquisition_halted",
  "takeover_state",
  "tier_changed",
  "config_applied",
]);

export type MaintenanceStore = ReturnType<typeof createMaintenanceStore>;

function fields(value: CommFields): CommFields {
  return { slave_id: value.slave_id, baudrate: value.baudrate, parity: value.parity };
}

export function createMaintenanceStore(api: ApiClient) {
  const state: MaintenanceStoreState = reactive({
    view: createResource<MaintenanceState>(),
    action: createResource<MaintenanceState>(),
    confirming: createResource<WriteConfirmation>(),
    pending: null,
    form: {
      serial_port: "",
      old: { slave_id: 1, baudrate: 19200, parity: "N" },
      new: { slave_id: 1, baudrate: 19200, parity: "N" },
      isolated: false,
    },
    formSource: null,
    nonZero: true,
    details: null,
    settings: createResource<SettingsComm>(),
  }) as MaintenanceStoreState;

  /** The form follows the service while a pending write locks it (the isolation box too: V1.0.3 disables it with the
   * tick the window had, so a reopened page cannot verify by hand, D-218 question 1, #57), and starts from the
   * defaults when the target changes; otherwise it keeps what was typed (V1.0.3's fields keep their values after a
   * verification). */
  function syncForm(view: MaintenanceState): void {
    const communication = view.communication;
    if (!communication) return;
    const target = view.target ?? "";
    const changed = target !== state.formSource;
    if (communication.form_locked || changed) {
      state.form.serial_port = communication.form.serial_port;
      state.form.old = fields(communication.form.old);
      state.form.new = fields(communication.form.new);
      if (changed) state.form.isolated = false;
      if (communication.form_locked) state.form.isolated = communication.isolated;
      state.formSource = target;
    }
  }

  function show(view: MaintenanceState | null): void {
    if (view === null) return;
    state.view.data = view;
    state.view.error = null;
    syncForm(view);
  }

  async function load(): Promise<boolean> {
    const ok = await run(state.view, () => api.maintenanceState());
    state.view.retry = load;
    if (ok && state.view.data) syncForm(state.view.data);
    return ok;
  }

  /** Run one action; its answer is the new view. */
  async function act(load: () => Promise<MaintenanceState>, retry: (() => Promise<boolean>) | null): Promise<boolean> {
    const ok = await run(state.action, load);
    state.action.retry = retry;
    if (ok) show(state.action.data);
    return ok;
  }

  /** A new page session is a new V1.0.3 window: its isolation box starts empty. */
  function open(tab = 0): Promise<boolean> {
    state.form.isolated = false;
    return act(() => api.openMaintenance(tab), () => open(tab));
  }
  const tab = (index: number): Promise<boolean> => act(() => api.maintenanceTab(index), () => tab(index));
  const target = (key: string): Promise<boolean> => act(() => api.maintenanceTarget(key), () => target(key));
  const refresh = (): Promise<boolean> => act(() => api.maintenanceAction("diagnostics/read"), refresh);
  const exportDiagnostics = (): Promise<boolean> => act(() => api.maintenanceAction("diagnostics/export"), exportDiagnostics);
  const discard = (): Promise<boolean> => act(() => api.maintenanceAction("calibration/discard"), discard);
  const dismissNotice = () => act(() => api.maintenanceAction("notice/dismiss"), null);
  const edit = (change: DraftEdit) => act(() => api.editCalibration(change), null);
  const commBody = (): Record<string, unknown> => ({
    serial_port: state.form.serial_port,
    old: fields(state.form.old),
    new: fields(state.form.new),
    isolated: state.form.isolated,
  });
  const commRead = (): Promise<boolean> => act(() => api.maintenanceAction("comm/read", commBody()), commRead);
  const commVerify = (): Promise<boolean> => act(() => api.maintenanceAction("comm/verify", commBody()), commVerify);

  /** A write: ask the service for its confirmation (it checks the conditions first), then show V1.0.3's text. */
  async function ask(path: string, body: Record<string, unknown> = {}, send: "post" | "close" = "post"): Promise<boolean> {
    const ok = await run(state.confirming, () => api.confirmMaintenance(path, body));
    state.confirming.retry = () => ask(path, body, send);
    const confirmation = state.confirming.data;
    if (ok && confirmation !== null) state.pending = { path, send, body, confirmation };
    return ok;
  }

  /** 是: send the write with the confirmation id; 否 (or Esc): nothing is sent. */
  async function answer(yes: boolean): Promise<boolean> {
    const pending = state.pending;
    state.pending = null;
    reset(state.confirming);
    if (!yes || pending === null) return false;
    const id = pending.confirmation.confirmation_id;
    if (pending.send === "close") return act(() => api.closeMaintenance(id), null);
    return act(() => api.writeMaintenance(pending.path, id, pending.body), null); // a used id cannot be retried
  }

  const enter = () => ask("enter");
  const leave = () => ask("leave");
  const writeCalibration = () => ask("calibration/write");
  const commWrite = () => ask("comm/write", commBody());

  /** 从硬件读取: with unwritten edits V1.0.3 asks first (G4). */
  async function readCalibration(): Promise<boolean> {
    if (state.view.data?.calibration?.dirty) return ask("calibration/read");
    return act(() => api.maintenanceAction("calibration/read", {}), readCalibration);
  }

  /** 关闭: with unwritten edits V1.0.3 asks first (G10). */
  async function close(): Promise<boolean> {
    if (state.view.data?.calibration?.dirty) return ask("page/close", {}, "close");
    return act(() => api.closeMaintenance(), close);
  }

  async function settingsComm(position: string): Promise<boolean> {
    const ok = await run(state.settings, () => api.settingsComm(position));
    state.settings.retry = () => settingsComm(position);
    return ok;
  }

  /** The settings page is left: V1.0.3 re-reads the current values on a reconnect only while it is shown. False
   * when the service did not answer (the page is gone, so nothing is shown; the service also stops the re-read when
   * the tier drops or the takeover ends). */
  async function settingsLeft(): Promise<boolean> {
    try {
      await api.settingsLeft();
      return true;
    } catch {
      return false;
    }
  }

  function onEvent(event: ServiceEvent): void {
    if (REFRESH_EVENTS.has(event.name)) void load();
  }

  function setNonZero(value: boolean): void {
    state.nonZero = value;
  }

  function showDetails(text: string | null): void {
    state.details = text;
  }

  return {
    state,
    load,
    open,
    close,
    tab,
    target,
    refresh,
    exportDiagnostics,
    readCalibration,
    edit,
    discard,
    writeCalibration,
    enter,
    commRead,
    commWrite,
    commVerify,
    leave,
    answer,
    dismissNotice,
    settingsComm,
    settingsLeft,
    onEvent,
    setNonZero,
    showDetails,
  };
}
