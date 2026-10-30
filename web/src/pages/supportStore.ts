/**
 * State of the support section of 设置与导出 (D-226): 导出诊断包 (API-27) and 维护记录 (API-28), every tier.
 *
 *   * the log is read when the section opens, on 刷新, and when the device filter or the time-sync choice changes;
 *     a failed read keeps the last list and offers a retry (R-1-5); a device whose database could not be read is
 *     named by the service (never shown as "no records");
 *   * 导出诊断包 writes one zip into the alpha's output folder; the service's text says where. A failure stays on
 *     the page with a retry (exporting again writes a new file, nothing is overwritten).
 * Every text comes from the service (contract 1.2).
 */
import { reactive } from "vue";
import type { ApiClient } from "../api/client";
import type { DiagnosticsExported, MaintenanceLog, MaintenanceLogDevice } from "../api/types";
import { createResource, run, type Resource } from "../lib/resource";

/** The device filter's value for "all devices". */
export const ALL_DEVICES = "";

export interface SupportState {
  log: Resource<MaintenanceLog>;
  /** p1..p4, or ALL_DEVICES */
  device: string;
  timeSync: boolean;
  /** the filter's choices: the devices of the last read of all devices (a filtered read lists only its own) */
  devices: MaintenanceLogDevice[];
  bundle: Resource<DiagnosticsExported>;
}

export type SupportStore = ReturnType<typeof createSupportStore>;

export function createSupportStore(api: ApiClient) {
  const state: SupportState = reactive({
    log: createResource<MaintenanceLog>(),
    device: ALL_DEVICES,
    timeSync: false,
    devices: [],
    bundle: createResource<DiagnosticsExported>(),
  }) as SupportState;

  async function loadLog(): Promise<boolean> {
    const query = { device: state.device === ALL_DEVICES ? null : state.device, timeSync: state.timeSync };
    const ok = await run(state.log, () => api.maintenanceLog(query));
    if (ok && query.device === null && state.log.data !== null) state.devices = state.log.data.devices;
    return ok;
  }

  async function setDevice(key: string): Promise<boolean> {
    state.device = key;
    return loadLog();
  }

  async function setTimeSync(on: boolean): Promise<boolean> {
    state.timeSync = on;
    return loadLog();
  }

  async function exportBundle(): Promise<boolean> {
    if (state.bundle.loading) return false;
    return run(state.bundle, () => api.exportDiagnostics());
  }

  return { state, loadLog, setDevice, setTimeSync, exportBundle };
}
