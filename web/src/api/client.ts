/**
 * Client of the local service /api/v0.
 *
 * Token: the shell opens the page as http://127.0.0.1:<port>/#token=<token> (service.json is read by the shell,
 * never by the page). The fragment never reaches the server; it is removed from the address bar at once and kept
 * in sessionStorage for reloads of this window only. Under `npm run dev` there is no token: the Vite proxy
 * (dev-proxy.ts) reads service.json and adds it.
 *
 * Errors: every failure becomes an ApiError with the service's {code, message, retryable, detail}; a request that
 * never got an answer (service stopped, network error) is `service_unavailable`, retryable.
 */
import type {
  ReferenceCurves,
  DiagnosticsExported,
  MaintenanceLog,
  MaintenanceLogQuery,
  DraftEdit,
  MaintenanceState,
  SettingsComm,
  WriteConfirmation,
  AcquisitionConfig,
  AcquisitionStatus,
  ConfigRequest,
  ImportPreview,
  LiveOverview,
  SerialPorts,
  TierConfirmation,
  TierState,
  AcquisitionDetail,
  AcquisitionExported,
  AcquisitionExportRequest,
  DeviceLog,
  DeviceSummary,
  ExportCount,
  ExportCountQuery,
  SettingsView,
  DeviceList,
  DliDay,
  ErrorBody,
  Health,
  HistoryPage,
  OperationCandidates,
  OperationComputation,
  OperationExported,
  OperationInputs,
  OperationKey,
  OperationNearest,
  OperationPage,
  OperationSources,
  Overview,
  SnapshotImported,
  SourceRef,
  SnapshotImportRequest,
  SnapshotList,
} from "./types";

export const API_PREFIX = "/api/v0";
const TOKEN_KEY = "par.token";
const TOKEN_FRAGMENT = /(?:^#|&)token=([^&]+)/;

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly retryable: boolean;
  readonly detail: string | null;

  constructor(status: number, body: ErrorBody) {
    super(body.message);
    this.name = "ApiError";
    this.status = status;
    this.code = body.code;
    this.retryable = body.retryable;
    this.detail = body.detail;
  }
}

function isErrorBody(value: unknown): value is { error: ErrorBody } {
  if (typeof value !== "object" || value === null || !("error" in value)) return false;
  const error = (value as { error: unknown }).error;
  return (
    typeof error === "object" &&
    error !== null &&
    typeof (error as ErrorBody).code === "string" &&
    typeof (error as ErrorBody).message === "string"
  );
}

interface TokenSources {
  location: Pick<Location, "hash" | "pathname" | "search">;
  history: Pick<History, "replaceState">;
  storage: Pick<Storage, "getItem" | "setItem"> | null;
}

/** The token from the URL fragment (then stripped from the address bar) or from this window's session storage. */
export function takeToken(sources: TokenSources): string | null {
  const match = TOKEN_FRAGMENT.exec(sources.location.hash);
  if (match?.[1]) {
    const token = decodeURIComponent(match[1]);
    sources.history.replaceState(null, "", sources.location.pathname + sources.location.search);
    try {
      sources.storage?.setItem(TOKEN_KEY, token);
    } catch {
      // storage blocked: the token still works for this page load
    }
    return token;
  }
  try {
    return sources.storage?.getItem(TOKEN_KEY) ?? null;
  } catch {
    return null;
  }
}

export function browserToken(): string | null {
  let storage: Storage | null = null;
  try {
    storage = window.sessionStorage;
  } catch {
    storage = null;
  }
  return takeToken({ location: window.location, history: window.history, storage });
}

export type Fetch = (input: string, init?: RequestInit) => Promise<Response>;

export interface HistoryQuery {
  start: string;
  end: string;
}

export class ApiClient {
  constructor(
    private readonly token: string | null,
    private readonly fetchImpl: Fetch = (input, init) => fetch(input, init),
    private readonly baseUrl = "",
  ) {}

  health(): Promise<Health> {
    return this.request<Health>("GET", "/health");
  }

  snapshots(): Promise<SnapshotList> {
    return this.request<SnapshotList>("GET", "/snapshots");
  }

  importSnapshot(body: SnapshotImportRequest): Promise<SnapshotImported> {
    return this.request<SnapshotImported>("POST", "/snapshots", body);
  }

  devices(): Promise<DeviceList> {
    return this.request<DeviceList>("GET", "/devices");
  }

  /** API-05 with offset 0 only: D-201 decided A (UI-046, no paging of the history list; owner 2026-10-18). */
  acquisitions(key: string, query: HistoryQuery): Promise<HistoryPage> {
    const params = new URLSearchParams({ start: query.start, end: query.end });
    return this.request<HistoryPage>("GET", `/devices/${encodeURIComponent(key)}/acquisitions?${params}`);
  }

  acquisition(key: string, id: number): Promise<AcquisitionDetail> {
    return this.request<AcquisitionDetail>("GET", `/devices/${encodeURIComponent(key)}/acquisitions/${id}`);
  }

  /** API-08: the four reference curves and the wavelength colours of the spectrum charts (fixed content). */
  referenceCurves(): Promise<ReferenceCurves> {
    return this.request<ReferenceCurves>("GET", "/reference-curves");
  }

  /** API-09 (read-only snapshot subset, D-211): the newest successful record with a spectrum, as the overview shows it. */
  overview(key: string): Promise<Overview> {
    return this.request<Overview>("GET", `/devices/${encodeURIComponent(key)}/latest`);
  }

  /** API-10: the current DLI period, or with `date` (YYYY-MM-DD) the period in progress at the end of that day. */
  dli(key: string, date: string | null = null): Promise<DliDay> {
    const query = date === null ? "" : `?${new URLSearchParams({ date })}`;
    return this.request<DliDay>("GET", `/devices/${encodeURIComponent(key)}/dli${query}`);
  }

  /** 保存经纬度并重置周期 (issue 116): stores the location of `key` and answers the shown period again. */
  saveDliLocation(key: string, latitude: number, longitude: number, date: string | null = null): Promise<DliDay> {
    const query = date === null ? "" : `?${new URLSearchParams({ date })}`;
    const path = `/devices/${encodeURIComponent(key)}/dli/location${query}`;
    return this.request<DliDay>("PUT", path, { latitude, longitude });
  }

  /** API-25: the calculation page's fixed texts, operations, axis ticks, guide and export folder. */
  operationPage(): Promise<OperationPage> {
    return this.request<OperationPage>("GET", "/operations/page");
  }

  /** API-11: the imported snapshots usable as A or B, with the initial A and B (UI-156). */
  operationSources(): Promise<OperationSources> {
    return this.request<OperationSources>("GET", "/operation-sources");
  }

  /** API-12: the newest 500 usable records of `key`; `keep` adds the still selected older record (UI-204). */
  operationSpectra(key: string, keep: number | null = null): Promise<OperationCandidates> {
    const query = keep === null ? "" : `?${new URLSearchParams({ keep: String(keep) })}`;
    return this.request<OperationCandidates>("GET", `/operation-sources/${encodeURIComponent(key)}/spectra${query}`);
  }

  /** API-13: the usable record of `key` closest in time to `acquiredAt` (the whole database, no tolerance). */
  operationNearest(key: string, acquiredAt: string): Promise<OperationNearest> {
    const query = new URLSearchParams({ acquired_at: acquiredAt });
    return this.request<OperationNearest>("GET", `/operation-sources/${encodeURIComponent(key)}/nearest?${query}`);
  }

  /** API-14 (inputs): the A and B charts and the time difference of a selection; writes nothing. */
  operationInputs(a: SourceRef | null, b: SourceRef | null): Promise<OperationInputs> {
    return this.request<OperationInputs>("POST", "/operations/inputs", { a, b });
  }

  /** API-14: A+B, A−B or A/B of two records; writes nothing. */
  operationCompute(a: SourceRef, b: SourceRef, operation: OperationKey): Promise<OperationComputation> {
    return this.request<OperationComputation>("POST", "/operations/compute", { a, b, operation });
  }

  /** API-24: write the result into a new folder of the alpha's output directory (D-207). */
  operationExport(a: SourceRef, b: SourceRef, operation: OperationKey, formats: string[]): Promise<OperationExported> {
    return this.request<OperationExported>("POST", "/operations/export", { a, b, operation, formats });
  }

  /** API-26: the read-only settings view and the export section's texts (tier 0, D-209). */
  settings(): Promise<SettingsView> {
    return this.request<SettingsView>("GET", "/settings");
  }

  /** API-15: records, database file, serial number and recorded poll cycle of a snapshot. */
  deviceSummary(key: string): Promise<DeviceSummary> {
    return this.request<DeviceSummary>("GET", `/devices/${encodeURIComponent(key)}/summary`);
  }

  /** API-16: the status line and the newest device log rows (tier 1; read only, asks the device nothing). */
  deviceLogs(key: string): Promise<DeviceLog> {
    return this.request<DeviceLog>("GET", `/devices/${encodeURIComponent(key)}/logs`);
  }

  /** API-22: the export preview; a preset range is recomputed by the service clock at every call (EXP-051). */
  exportCount(key: string, query: ExportCountQuery): Promise<ExportCount> {
    const params = new URLSearchParams({ range: query.range });
    if (query.start !== undefined) params.set("start", query.start);
    if (query.end !== undefined) params.set("end", query.end);
    for (const kind of query.formats) params.append("formats", kind);
    return this.request<ExportCount>("GET", `/devices/${encodeURIComponent(key)}/export/count?${params}`);
  }

  /** API-23: write the confirmed range into the alpha's output folder (D-210). */
  exportAcquisitions(key: string, body: AcquisitionExportRequest): Promise<AcquisitionExported> {
    return this.request<AcquisitionExported>("POST", `/devices/${encodeURIComponent(key)}/export`, body);
  }

  /* ------------------------------------------------ support (D-226), every tier */

  /** API-27: write a diagnostics zip into the alpha's output folder (logs, versions, configuration, status, audit
   * tables; no token, local folders replaced). Reads devices and databases only. */
  exportDiagnostics(): Promise<DiagnosticsExported> {
    return this.request<DiagnosticsExported>("POST", "/support/diagnostics-bundle");
  }

  /** API-28: the device writes recorded in the alpha's device databases, newest first (read only). */
  maintenanceLog(query: MaintenanceLogQuery): Promise<MaintenanceLog> {
    const params = new URLSearchParams();
    if (query.device !== null) params.set("device", query.device);
    if (query.timeSync) params.set("time_sync", "true");
    const text = params.toString();
    const suffix = text === "" ? "" : `?${text}`;
    return this.request<MaintenanceLog>("GET", `/support/maintenance-log${suffix}`);
  }

  /* ------------------------------------------------ tier 1 "接管采集" (16_ section 5) */

  /** The status bar's fixed block: tier, takeover and the text the service wrote (16_ 4.4). */
  tier(): Promise<TierState> {
    return this.request<TierState>("GET", "/tier");
  }

  /** First step of 0 → 1: the service issues a one-time confirmation (60 s) with both layers' texts. */
  confirmTier(tier: number): Promise<TierConfirmation> {
    return this.request<TierConfirmation>("POST", "/tier/confirmations", { tier });
  }

  /** 0 → 1 with the confirmation id; 1 → 0 without (202 while a running takeover is stopped first). */
  setTier(tier: number, confirmationId: string | null = null): Promise<TierState> {
    return this.request<TierState>("PUT", "/tier", { tier, confirmation_id: confirmationId });
  }

  acquisitionConfig(): Promise<AcquisitionConfig> {
    return this.request<AcquisitionConfig>("GET", "/acquisition-config");
  }

  /** V1.0.3's DeviceHub.apply on the service: its own checks and messages decide (400 with V1.0.3's text). */
  saveAcquisitionConfig(body: ConfigRequest): Promise<AcquisitionConfig> {
    return this.request<AcquisitionConfig>("PUT", "/acquisition-config", body);
  }

  /** V1.0.3's 刷新串口: the computer's serial ports; the service only enumerates them, it opens none (#74). */
  serialPorts(): Promise<SerialPorts> {
    return this.request<SerialPorts>("GET", "/acquisition-config/serial-ports");
  }

  /** Reads a V1.0.3 configuration and writes nothing (16_ 3.3). */
  importPreview(sourcePath: string): Promise<ImportPreview> {
    return this.request<ImportPreview>("POST", "/acquisition-config/import-preview", { source_path: sourcePath });
  }

  startAcquisition(): Promise<AcquisitionStatus> {
    return this.request<AcquisitionStatus>("POST", "/acquisition/start");
  }

  stopAcquisition(): Promise<AcquisitionStatus> {
    return this.request<AcquisitionStatus>("POST", "/acquisition/stop");
  }

  acquisitionStatus(): Promise<AcquisitionStatus> {
    return this.request<AcquisitionStatus>("GET", "/acquisition/status");
  }

  liveOverview(key: string): Promise<LiveOverview> {
    return this.request<LiveOverview>("GET", `/acquisition/devices/${encodeURIComponent(key)}/latest`);
  }

  /* ------------------------------------------------ tier 2 "设备维护" (17_ section 9) */

  maintenanceState(): Promise<MaintenanceState> {
    return this.request<MaintenanceState>("GET", "/maintenance/state");
  }

  openMaintenance(tab: number): Promise<MaintenanceState> {
    return this.request<MaintenanceState>("POST", "/maintenance/page", { tab });
  }

  closeMaintenance(confirmationId: string | null = null): Promise<MaintenanceState> {
    const query = confirmationId === null ? "" : `?${new URLSearchParams({ confirmation_id: confirmationId })}`;
    return this.request<MaintenanceState>("DELETE", `/maintenance/page${query}`);
  }

  maintenanceTab(tab: number): Promise<MaintenanceState> {
    return this.request<MaintenanceState>("POST", "/maintenance/tab", { tab });
  }

  maintenanceTarget(key: string): Promise<MaintenanceState> {
    return this.request<MaintenanceState>("PUT", "/maintenance/target", { key });
  }

  /** A maintenance action without a confirmation (`path` under /maintenance). */
  maintenanceAction(path: string, body: unknown = {}): Promise<MaintenanceState> {
    return this.request<MaintenanceState>("POST", `/maintenance/${path}`, body);
  }

  editCalibration(edit: DraftEdit): Promise<MaintenanceState> {
    return this.request<MaintenanceState>("PATCH", "/maintenance/calibration/draft", edit);
  }

  /** First step of a write: the service checks the conditions and answers V1.0.3's dialog text with an id. */
  confirmMaintenance(path: string, body: unknown = {}): Promise<WriteConfirmation> {
    return this.request<WriteConfirmation>("POST", `/maintenance/${path}/confirmations`, body);
  }

  /** The write itself, with the confirmation id and the same body (409 confirmation_required otherwise). */
  writeMaintenance(path: string, confirmationId: string, body: Record<string, unknown> = {}): Promise<MaintenanceState> {
    return this.request<MaintenanceState>("POST", `/maintenance/${path}`, { ...body, confirmation_id: confirmationId });
  }

  settingsComm(position: string): Promise<SettingsComm> {
    return this.request<SettingsComm>("POST", `/acquisition/devices/${encodeURIComponent(position)}/comm/read`);
  }

  /** Leaving the settings page: the service stops its automatic re-read on a reconnect (204, no body). */
  async settingsLeft(): Promise<void> {
    const response = await this.send("DELETE", "/acquisition/devices/comm/read", undefined);
    if (!response.ok) throw await this.failure(response, await response.json().catch(() => null));
  }

  /** API-17: the event stream, read with fetch so the token goes in a header, never in the address (16_ 5). */
  async openEvents(signal: AbortSignal): Promise<ReadableStream<Uint8Array>> {
    const response = await this.send("GET", "/events", undefined, "text/event-stream", signal);
    if (response.ok && response.body) return response.body;
    throw await this.failure(response, null);
  }

  private async send(
    method: string,
    path: string,
    body: unknown,
    accept = "application/json",
    signal?: AbortSignal,
  ): Promise<Response> {
    const headers: Record<string, string> = { Accept: accept };
    if (this.token) headers["X-PAR-Token"] = this.token;
    if (body !== undefined) headers["Content-Type"] = "application/json";
    try {
      return await this.fetchImpl(`${this.baseUrl}${API_PREFIX}${path}`, {
        method,
        headers,
        body: body === undefined ? undefined : JSON.stringify(body),
        cache: "no-store",
        credentials: "omit",
        signal,
      });
    } catch (error) {
      throw new ApiError(0, {
        code: "service_unavailable",
        message: "无法连接本机服务，请确认程序仍在运行",
        retryable: true,
        detail: String(error),
      });
    }
  }

  private async failure(response: Response, payload: unknown): Promise<ApiError> {
    let body = payload;
    if (body === null) {
      try {
        body = await response.json();
      } catch {
        body = null;
      }
    }
    if (isErrorBody(body)) return new ApiError(response.status, body.error);
    return new ApiError(response.status, {
      code: response.ok ? "invalid_response" : "internal",
      message: `本机服务返回了无法识别的应答（HTTP ${response.status}）`,
      retryable: true,
      detail: null,
    });
  }

  private async request<T>(method: string, path: string, body?: unknown): Promise<T> {
    const response = await this.send(method, path, body);
    let payload: unknown = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    if (response.ok && payload !== null) return payload as T;
    throw await this.failure(response, payload);
  }
}
