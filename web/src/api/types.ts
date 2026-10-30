/**
 * Response shapes of /api/v0 (docs/spec/api-contract-v0.md; schema docs/spec/openapi-v0.json).
 * Display texts come from the service; the page shows `*_text` / `text` fields as they are (contract 1.2).
 */

export type Source = "snapshot" | "live_ro" | "live";

export interface ErrorBody {
  code: string;
  message: string;
  retryable: boolean;
  detail: string | null;
}

export interface Health {
  status: "ok";
  version: string;
  build_commit: string | null;
  tier: number;
  started_at: string;
}

export interface Fingerprint {
  size: number;
  mtime_ns: number;
  sha256: string;
}

export interface Snapshot {
  id: string;
  name: string;
  key: string;
  position: number;
  file_name: string;
  path: string;
  source_path: string;
  imported_at: string;
  record_count: number;
  source_before: Fingerprint;
  source_after: Fingerprint;
  source_changed_during_import: boolean;
}

export interface SnapshotList {
  as_of: string;
  source: Source;
  items: Snapshot[];
}

export interface SnapshotImported {
  as_of: string;
  source: Source;
  snapshot: Snapshot;
}

export interface SnapshotImportRequest {
  source_path: string;
  name?: string | null;
  position?: number;
}

export type DisplayState = "normal" | "disabled" | "fault" | "unconfigured";

export interface Device {
  key: string;
  position: number;
  configured: boolean;
  enabled: boolean;
  name: string;
  address_text: string | null;
  display_state: DisplayState;
  database_name: string | null;
  database_path: string | null;
  snapshot_id: string | null;
  imported_at: string | null;
}

export interface DeviceList {
  as_of: string;
  source: Source;
  tier: number;
  items: Device[];
}

export interface TimeRange {
  start: string;
  end: string;
}

export interface HistoryItem {
  seq: number;
  id: number;
  acquired_at: string;
  acquired_at_text: string;
  success: boolean;
  result_text: string;
  exposure_status: number | null;
  exposure_text: string;
  exposure_style: "normal" | "warn";
}

export interface HistoryPage {
  as_of: string;
  source: Source;
  snapshot_id: string;
  range: TimeRange;
  limit: number;
  offset: number;
  limit_reached: boolean;
  next_offset: number | null;
  items: HistoryItem[];
}

export interface MetricItem {
  key: string;
  label: string;
  unit: string;
  text: string;
}

export interface MetricGroup {
  title: string;
  items: MetricItem[];
}

export interface Spectrum {
  wavelength_start: number;
  wavelength_step: number;
  spectral_coefficient: number | null;
  points: number[];
  values: number[];
}

/** API-08: the four reference curves (UI-168) and the wavelength-coloured fill (UI-317), fixed content. */
export interface ReferenceCurve {
  key: "chlorophyll_a" | "chlorophyll_b" | "mccree" | "photopic";
  /** legend text, as in V1.0.x */
  label: string;
  line: "dashed" | "dotted" | "dashdot";
  width: number;
  x: number[];
  /** normalised, on the right response axis */
  y: number[];
}

export interface ReferenceCurves {
  curves: ReferenceCurve[];
  axis_label: string;
  /** top of the right axis (bottom 0) */
  axis_max: number;
  /** wavelength (nm) of fill_colors[0]; each further entry +1 nm */
  fill_start: number;
  /** [R, G, B] 0–1 per wavelength; segment x_i..x_i+1 takes colour i */
  fill_colors: number[][];
  fill_opacity: number;
}

export interface DetailHeader {
  title: string;
  time_text: string;
  status_text: string;
  status_level: "ok" | "warn" | "error";
  exposure_text: string;
}

export interface AcquisitionDetail {
  as_of: string;
  source: Source;
  snapshot_id: string;
  device: { key: string; name: string };
  header: DetailHeader;
  success: boolean;
  elapsed_text: string;
  review_text: string;
  groups: MetricGroup[];
  record: Record<string, number | string | null>;
  spectrum_state: "ok" | "none" | "invalid";
  spectrum: Spectrum | null;
}

/** API-10 (光积累计算): one integration period, everything computed by the service with the V1.0.3 rules. */
export interface DliPeriod {
  start: string;
  end: string;
  /** Beijing date of the period start, shown in the date picker */
  date: string;
  current: boolean;
  text: string;
}

export interface DliLocation {
  latitude: number;
  longitude: number;
  stored: boolean;
  coordinates_text: string;
  text: string;
}

export interface DliEnabled {
  at: string;
  stored: boolean;
  text: string;
}

export type DliStateText = "积分中" | "部分累计" | "有效数据不足";
export type DliStateLevel = "ok" | "warn" | "muted";

export interface DliSummary {
  total: number;
  covered_seconds: number;
  missing_seconds: number;
  coverage: number;
  first_valid: string | null;
  last_valid: string | null;
  integrated_until: string | null;
  head_seconds: number;
  internal_seconds: number;
  tail_seconds: number;
  cutoff: string;
  state: DliStateText;
  stale: boolean;
  paused: boolean;
}

export interface DliHeader {
  total_text: string;
  state_text: string;
  state_level: DliStateLevel;
  times_text: string;
  coverage_text: string;
  coverage_tooltip: string;
}

export interface DliSeries {
  times: string[];
  offsets_seconds: number[];
  /** null breaks the curve (DLI-049); never filled with zero */
  cumulative: (number | null)[];
}

export interface DliMetric {
  key: string;
  title: string;
  summary: DliSummary;
  header: DliHeader;
  y_max: number;
  series: DliSeries;
}

export interface DliTick {
  offset_seconds: number;
  at: string;
  text: string;
  narrow: boolean;
}

export interface DliInterruption {
  occurred_at: string;
  occurred_at_text: string;
  reason: string;
}

export interface DliDay {
  as_of: string;
  source: Source;
  snapshot_id: string;
  device: { key: string; name: string };
  requested_date: string | null;
  period: DliPeriod;
  location: DliLocation;
  enabled: DliEnabled;
  observed_until: string;
  /** From the latest successful record's quality_json (D-204 question 1 = D, D-206); 60 s when unusable. */
  poll_cycle_seconds: number;
  poll_cycle_source: "record" | "default";
  poll_cycle_record_at: string | null;
  max_gap_seconds: number;
  gap_text: string;
  snapshot_text: string;
  paused: boolean;
  metrics: DliMetric[];
  interruptions: DliInterruption[];
  ticks: DliTick[];
}

/* --- 光谱计算 (API-11..14, API-24, API-25) ----------------------------------------------------------------- */

export type OperationKey = "add" | "subtract" | "divide";
export type ExportKind = "csv" | "xlsx";
export type Range = [number, number];

export interface OperationTexts {
  source_labels: string[];
  operation_label: string;
  run_label: string;
  export_label: string;
  swap_tooltip: string;
  auto_match_label: string;
  auto_match_tooltip: string;
  time_tooltip: string;
  no_spectrum: string;
  input_empty_heading: string;
  input_empty_detail: string;
  waiting_heading: string;
  missing_heading: string;
  missing_detail: string;
  result_title: string;
  x_label: string;
  power_y_label: string;
  empty_sources: string;
}

export interface OperationAxis {
  start_nm: number;
  end_nm: number;
  ticks_wide: number[];
  ticks_narrow: number[];
  narrow_below_px: number;
}

export interface GuideParagraph {
  head: string | null;
  text: string;
}

export interface GuideSection {
  anchor: string | null;
  title: string;
  paragraphs: GuideParagraph[];
  links: { text: string; url: string }[];
}

export interface OperationGuide {
  title: string;
  details_button: string;
  close_button: string;
  summary: GuideParagraph[];
  navigation: { text: string; anchor: string }[];
  intro: string;
  sections: GuideSection[];
  dialog: { width_px: number; height_px: number; screen_fraction: number };
}

export interface OperationExportTexts {
  title: string;
  formats_label: string;
  formats: { key: ExportKind; label: string; checked: boolean }[];
  cancel_label: string;
  confirm_label: string;
  note: string;
  done_title: string;
  failed_title: string;
  directory: string;
}

export interface OperationPage {
  as_of: string;
  source: Source;
  title: string;
  operations: { key: OperationKey; label: string }[];
  default_operation: OperationKey;
  texts: OperationTexts;
  axis: OperationAxis;
  guide: OperationGuide;
  export: OperationExportTexts;
}

export interface OperationSourceItem {
  key: string;
  position: number;
  device_name: string;
  snapshot_id: string;
  database_path: string;
  source_path: string;
  imported_at: string;
  display_state: "normal" | "disabled" | "fault" | "unconfigured";
  tooltip: string;
}

export interface OperationSources {
  as_of: string;
  source: Source;
  items: OperationSourceItem[];
  initial_a: string | null;
  initial_b: string | null;
}

export interface OperationCandidate {
  id: number;
  acquired_at: string;
  acquired_at_text: string;
  label: string;
}

export interface OperationCandidates {
  as_of: string;
  source: Source;
  key: string;
  snapshot_id: string;
  limit: number;
  items: OperationCandidate[];
  empty_text: string;
}

export interface OperationNearest {
  as_of: string;
  source: Source;
  key: string;
  snapshot_id: string;
  match: (OperationCandidate & { time_difference_seconds: number | null }) | null;
}

export interface SourceRef {
  source: string;
  id: number;
  snapshot_id?: string | null;
}

export interface OperationInput {
  label: string;
  source: string | null;
  snapshot_id: string | null;
  id: number | null;
  valid: boolean;
  title: string;
  legend: string;
  device_name: string | null;
  acquired_at: string | null;
  acquired_at_text: string | null;
  y_range: Range | null;
  values: number[] | null;
}

export interface OperationInputs {
  as_of: string;
  source: Source;
  a: OperationInput;
  b: OperationInput;
  valid: boolean;
  time_difference: { seconds: number | null; text: string; tooltip: string };
  placeholder: { heading: string; detail: string };
}

export interface OperationResult {
  operation: OperationKey;
  operation_label: string;
  title: string;
  legend: string;
  y_label: string;
  ratio: boolean;
  values: (number | null)[];
  plotted: (number | null)[];
  y_range: Range;
  reference_line: boolean;
  ratio_note: string | null;
  empty_text: string | null;
  threshold: number | null;
}

export interface OperationComputation extends OperationInputs {
  result: OperationResult;
}

export interface OperationExported {
  as_of: string;
  directory: string;
  files: string[];
  text: string;
}

/* ---- settings page (API-26 read-only view, API-15 summary, API-22 count, API-23 export; D-209, D-210) ---- */

export interface BusField {
  label: string;
  text: string;
}

export interface SettingsDevice {
  key: string;
  position: number;
  configured: boolean;
  state_text: string | null;
  name: string;
  slave_id_text: string | null;
  enabled_text: string | null;
  fail_stop_text: string | null;
  database_name: string | null;
  database_path: string | null;
  snapshot_path: string | null;
  snapshot_id: string | null;
  imported_at: string | null;
  tooltip: string | null;
}

export interface RangeOption {
  key: string;
  label: string;
}

export interface ExportTexts {
  title: string;
  device_label: string;
  range_label: string;
  start_label: string;
  end_label: string;
  count_label: string;
  content_label: string;
  formats_label: string;
  ranges: RangeOption[];
  default_range: string;
  formats: { key: ExportKind; label: string; checked: boolean }[];
  content_note: string;
  content_tooltip: string;
  button_label: string;
  counting_text: string;
  no_device_text: string;
  done_title: string;
  failed_title: string;
  directory: string;
  note: string;
}

export interface SettingsView {
  as_of: string;
  source: Source;
  tier: number;
  title: string;
  groups: string[];
  read_only_text: string;
  config_text: string;
  config_note: string;
  bus: BusField[];
  device_columns: string[];
  devices: SettingsDevice[];
  export: ExportTexts;
}

export interface DeviceSummary {
  as_of: string;
  source: Source;
  snapshot_id: string;
  device: { key: string; name: string };
  total: number;
  latest: string | null;
  records_text: string;
  database_name: string;
  database_size_text: string;
  database_text: string;
  serial_text: string;
  status_text: string;
  poll_cycle_text: string;
}

/** API-16 status line: V1.0.3's connection_status_label (GitHub issue 107). */
export interface DeviceStatusLine {
  text: string;
  level: string;
  tone: "normal" | "warning" | "error" | "muted";
  tooltip: string;
}

/** API-16: one row of the device log table (UI-078..079, UI-100, UI-279, UI-280). */
export interface LogEntry {
  id: number | null;
  occurred_at: string | null;
  time_text: string;
  level: string | null;
  category: string;
  category_text: string;
  category_tooltip: string;
  message: string;
  result_text: string;
  result_tooltip: string;
  details: string | null;
  error: boolean;
  details_text: string;
}

/** API-16: 设备状态与最近日志 of one device (tier 1). */
export interface DeviceLog {
  as_of: string;
  source: Source;
  snapshot_id: string;
  device: { key: string; name: string };
  status: DeviceStatusLine;
  columns: string[];
  details_title: string;
  copy_label: string;
  items: LogEntry[];
}

export interface ExportRange {
  mode: string;
  start: string;
  end: string;
  start_text: string;
  end_text: string;
  editable: boolean;
}

export interface ExportConfirmation {
  title: string;
  text: string;
  records: number;
  files: number;
}

export interface ExportCount {
  as_of: string;
  source: Source;
  snapshot_id: string;
  device: { key: string; name: string };
  range: ExportRange;
  formats: ExportKind[];
  count: number;
  files: number;
  text: string;
  can_export: boolean;
  confirm: ExportConfirmation | null;
  notice: string | null;
}

export interface ExportCountQuery {
  range: string;
  start?: string;
  end?: string;
  formats: ExportKind[];
}

export interface AcquisitionExportRequest {
  start: string;
  end: string;
  formats: ExportKind[];
  snapshot_id: string | null;
  /** the confirmation's record count: a range that gained records meanwhile is refused (EXP-052, #82) */
  records?: number;
}

export interface AcquisitionExported {
  as_of: string;
  directory: string;
  device_folder: string;
  records: number;
  files: number;
  text: string;
}

/** API-09 (read-only snapshot subset, D-211): fixed texts of the overview page, copied from the V1.0.3 window. */
export interface OverviewTexts {
  page_title: string;
  summary_title: string;
  summary_context: string;
  details_button: string;
  metrics_toggle: string;
  spectrum_title: string;
  x_label: string;
  y_label: string;
  empty_heading: string;
  empty_detail: string;
  invalid_spectrum: string;
  details_columns: string[];
  details_close: string;
}

export interface OverviewKpi {
  key: string;
  title: string;
  text: string;
}

export interface OverviewRecord {
  id: number;
  acquired_at: string | number | null;
  acquired_at_text: string;
  age_seconds: number | null;
  age_text: string;
  exposure_text: string;
  elapsed_text: string;
  review_text: string;
  details_title: string;
}

export interface OverviewAttempt {
  id: number;
  success: boolean;
  acquired_at: string | number | null;
  acquired_at_text: string;
}

export type OverviewLevel = "ok" | "warn" | "error" | "none";

export interface MetricRow {
  label: string;
  text: string;
}

export interface OverviewTableGroup {
  title: string;
  rows: MetricRow[];
}

export interface OverviewChart {
  title: string;
  spectrum_state: "ok" | "none" | "invalid";
  spectrum: Spectrum | null;
  y_max: number | null;
  x_ticks: number[];
  overlay: MetricRow[][];
}

export interface Overview {
  as_of: string;
  source: Source;
  snapshot_id: string;
  device: { key: string; name: string };
  snapshot_text: string;
  texts: OverviewTexts;
  display_record: OverviewRecord | null;
  latest_attempt: OverviewAttempt | null;
  status: { text: string; level: OverviewLevel };
  stale: boolean | null;
  stale_after_seconds: number;
  poll_cycle_seconds: number;
  poll_cycle_source: "record" | "default";
  poll_cycle_text: string;
  kpis: OverviewKpi[];
  core_metrics: MetricRow[];
  table: OverviewTableGroup[];
  chart: OverviewChart;
  details_enabled: boolean;
  metrics_error: { message: string; detail: string } | null;
}

/* ---------------------------------------------------------------- tier 1 "接管采集" (16_ section 5; D-212..D-214) */

export type TierLevel = "muted" | "info" | "warn" | "error" | "maintenance";
export type Takeover = "released" | "starting" | "running" | "stopping";

/** GET /tier: the status bar's fixed block (16_ 4.4); the text and its colour come from the service. */
export interface TierState {
  tier: number;
  takeover: Takeover;
  lock_held: boolean;
  text: string;
  level: TierLevel;
  settings_path: string;
  settings_problem: string | null;
  /** "停止采集" confirmation; with a halt it repeats the halt text (review Q1) */
  stop_text: string;
  /** "切回档位 0" confirmation */
  down_text: string;
  /** "切回档位 1" (from 2) confirmation (17_ 6.1) */
  down_to_1_text: string;
  /** taken over and in communication maintenance */
  maintenance: boolean;
  /** the service's last unexpected error in this run (D-225 item 1); null when there was none */
  fault: ServiceFault | null;
}

/** An unexpected error of the service (D-225 item 1, R-1-5; GET /tier `fault`, event `service_error`). */
export interface ServiceFault {
  /** 1, 2, … within one service run */
  id: number;
  /** request: a request failed, the page keeps its data and can retry; takeover: the service stopped the takeover
   * and wrote tier 0 */
  kind: "request" | "takeover";
  occurred_at: string;
  where: string;
  /** the exception's type name (the traceback is in service.log) */
  error: string;
  /** the full text to show */
  message: string;
  stopping: boolean;
}

/** POST /tier/confirmations: the two layers of the second confirmation, valid 60 s, usable once (16_ 4.2). */
export interface TierConfirmation {
  confirmation_id: string;
  tier: number;
  expires_at: string;
  notice: string;
  confirmation: string;
}

export interface BusValues {
  transport: "rtu" | "tcp";
  serial_port: string;
  host: string;
  tcp_port: number;
  baudrate: number;
  parity: "N" | "E" | "O";
  timeout_seconds: number;
  poll_cycle_seconds: number;
}

export interface ConfigRow {
  name: string;
  slave_id: number;
  enabled: boolean;
  auto_stop_on_failure: boolean;
  database_path: string;
  database_name: string | null;
  registered: boolean;
  /** reuse the same-name database of the alpha's devices folder (D-215); always false when read */
  reuse_existing: boolean;
}

export interface Choice {
  value: string;
  label: string;
}

/** V1.0.3's settings form as the service gives it (labels, choices, ranges, hints): the page writes no rule. */
export interface ConfigForm {
  labels: { key: string; label: string }[];
  transports: Choice[];
  baudrates: number[];
  parities: Choice[];
  parity_tooltip: string;
  poll_min: number;
  poll_max: number;
  poll_decimals: number;
  poll_hint: string;
  poll_tooltip: string;
  slave_min: number;
  slave_max: number;
  tcp_port_min: number;
  tcp_port_max: number;
  device_columns: string[];
  name_placeholders: string[];
  enabled_tooltip: string;
  fail_stop_tooltip: string;
  save_label: string;
  save_tooltip: string;
  saved_text: string;
  error_title: string;
  serial_port_hint: string;
  new_database_text: string;
  save_requires_running: string;
  reuse_label: string;
  reuse_tooltip: string;
  /** the configuration cannot be used (D-220): V1.0.3's startup question, adapted */
  reconfigure_title: string;
  reconfigure_text: string;
  reconfigure_label: string;
  reconfigure_hint: string;
  /** a saved configuration failed to apply in the background (D-221) */
  apply_failed_text: string;
}

/** Why the alpha's configuration cannot be used (file unreadable, database outside the alpha folder, or a database
 * the last 开始采集 found unusable); null when it can (D-220). */
export interface ConfigProblem {
  message: string;
  detail: string | null;
}

export interface AcquisitionConfig {
  as_of: string;
  path: string;
  exists: boolean;
  configured: boolean;
  bus: BusValues;
  poll_cycle_seconds: number;
  devices: {
    name: string;
    slave_id: number;
    enabled: boolean;
    auto_stop_on_failure: boolean;
    database_path: string;
    database_name: string;
    database_exists: boolean;
    inside_alpha: boolean;
  }[];
  devices_dir: string;
  rows: ConfigRow[];
  /** the form V1.0.3 starts from after "重新配置": an empty configuration (D-220) */
  blank_bus: BusValues;
  blank_rows: ConfigRow[];
  problem: ConfigProblem | null;
  form: ConfigForm;
}

export interface ConfigRequest {
  bus: BusValues;
  devices: Omit<ConfigRow, "database_name" | "registered">[];
  /** save from an empty configuration with nothing taken over; only while `problem` is set (D-220) */
  reconfigure: boolean;
}

export interface ImportDevice {
  name: string;
  slave_id: number;
  enabled: boolean;
  auto_stop_on_failure: boolean;
  source_database_path: string;
  importable: boolean;
  problem: string | null;
}

/** One of the computer's serial ports (V1.0.3's 刷新串口): `value` is saved, `label` is shown in the list. */
export interface SerialPort {
  value: string;
  label: string;
}

/** GET /acquisition-config/serial-ports (#74): the operating system's order; enumerated only, no port opened. */
export interface SerialPorts {
  as_of: string;
  ports: SerialPort[];
  /** V1.0.3's tooltip after a refresh: how many ports were found, or none */
  hint: string;
}

export interface ImportPreview {
  as_of: string;
  source_path: string;
  bus: BusValues;
  devices: ImportDevice[];
  rows: ConfigRow[];
  note: string;
}

/** Where a shown message is recorded (issue 136): its run event in logs/events.jsonl and the diagnostics bundle. */
export interface Notice {
  /** "<会话>-<序号>": a random session per service start, numbers from 1; a restart never repeats one */
  event_id: string;
  /** when the message appeared (Beijing time); says nothing about whether it still holds */
  occurred_at: string;
}

export interface RuntimeDevice {
  key: string;
  position: string | null;
  name: string;
  slave_id: number;
  enabled: boolean;
  online: boolean;
  level: string;
  message: string;
  failures: number;
  excluded: boolean;
  last_failure_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
  latest_record_id: number | null;
  database_path: string;
  status_text: string;
  /** the record of `message`; null when there is none */
  notice?: Notice | null;
}

export interface Halt {
  name: string | null;
  slave_id: number | null;
  occurred_at: string | null;
  reason: string | null;
  text: string;
  notice?: Notice | null;
}

export type RunLevel = "ok" | "warn" | "error" | "muted";

/** GET /acquisition/status `run_status`: V1.0.3's top-bar block, word for word (issue #73). */
export interface RunStatus {
  /** "总线：<摘要>" (MainWindow._on_bus_state); `detail` is the bus message, V1.0.3's tooltip. `devices_silent`:
   *  no enabled device answers, so 总线：异常 although the port is open (issue 131, not V1.0.3) */
  bus: { text: string; level: RunLevel; detail: string; notice?: Notice | null; devices_silent?: boolean };
  /** the acquisition state (MainWindow._refresh_communication_events); a halt's carries the halt's notice */
  acquisition: { text: string; level: RunLevel; notice?: Notice | null };
  /** V1.0.3's red lines, one per enabled device with consecutive failures; empty when there are none */
  failures: string[];
  /** the record of each failure line, in the same order (issue 136) */
  failure_notices?: (Notice | null)[];
}

/** GET /acquisition/status: the state cache (16_ section 5); events only say "look again". */
export interface AcquisitionStatus {
  as_of: string;
  takeover: Takeover;
  lock_held: boolean;
  error: string | null;
  error_notice?: Notice | null;
  bus: { level: string; message: string; notice?: Notice | null };
  halt: Halt | null;
  maintenance: boolean;
  poll_cycle_seconds: number | null;
  /** "应用配置失败：<原因>" until a configuration is applied or the next start; the old one still runs (D-221) */
  config_apply_error: string | null;
  devices: RuntimeDevice[];
  run_status: RunStatus;
  /** logs/events.jsonl (issue 136): records the file lost (queue full, failed write) are counted here */
  event_log?: EventLogHealth | null;
}

export interface EventLogHealth {
  session: string;
  written: number;
  last_written_sequence: number | null;
  dropped: number;
  failed: number;
  first_error: string | null;
  last_error: string | null;
}

/** GET /acquisition/devices/{key}/latest: the overview of the alpha's own database (source live, D-213 q4). */
export interface LiveOverview {
  as_of: string;
  source: Source;
  /** this database of this position (API-06's snapshot_id): 全部指标 shows only a detail of the same one (issue 106) */
  snapshot_id: string;
  device: { key: string; name: string; database_path: string };
  texts: OverviewTexts;
  display_record: OverviewRecord | null;
  latest_attempt: OverviewAttempt | null;
  status: { text: string; level: OverviewLevel };
  paused: boolean;
  stale: boolean | null;
  stale_after_seconds: number;
  poll_cycle_seconds: number;
  kpis: OverviewKpi[];
  core_metrics: MetricRow[];
  table: OverviewTableGroup[];
  chart: OverviewChart;
  details_enabled: boolean;
  metrics_error: { message: string; detail: string } | null;
}

/** One message of GET /events (API-17). */
export interface ServiceEvent {
  id: number | null;
  name: string;
  data: Record<string, unknown>;
}

/* ------------------------------------------------------------ tier 2 "设备维护" (17_ section 9) */

export interface MaintenanceDevice {
  key: string;
  label: string;
  position: string | null;
}

export interface DiagnosticRow {
  category: string;
  name: string;
  count: string;
  delta: string;
  zero: boolean;
  tooltip: string;
}

export interface DiagnosticEvent {
  time: string;
  level: string;
  operation: string;
  message: string;
  details: string;
}

export interface MaintenanceDiagnostics {
  stamp: string;
  identity: string;
  values: string;
  exposure: string;
  data: string;
  has_snapshot: boolean;
  historical: boolean;
  rows: DiagnosticRow[];
  empty_text: string;
  refresh_enabled: boolean;
  read_reason: string;
  export_text: string;
  export_enabled: boolean;
  events: DiagnosticEvent[];
}

export interface CalibrationField {
  name: string;
  caption: string;
  decimals: number;
  text: string;
  minimum: number;
  maximum: number;
  enabled: boolean;
}

export interface CalibrationCurve {
  x: number[];
  y: number[];
  nodes: [number, number][];
  global_percent: number;
  limit_min_percent: number;
  limit_max_percent: number;
}

export interface MaintenanceCalibration {
  fields: CalibrationField[];
  read_enabled: boolean;
  write_enabled: boolean;
  discard_enabled: boolean;
  editable: boolean;
  dirty: boolean;
  version: number;
  value_state: string;
  value_state_error: boolean;
  history: boolean;
  note: string;
  note_error: boolean;
  status: string;
  status_tooltip: string;
  error: string;
  error_tooltip: string;
  version_text: string;
  time: string;
  curve: CalibrationCurve | null;
  out_of_order: boolean;
  out_of_order_text: string;
  unavailable_reason: string;
}

export interface CommFields {
  slave_id: number;
  baudrate: number;
  parity: string;
}

export interface CommForm {
  serial_port: string;
  old: CommFields;
  new: CommFields;
  isolated: boolean;
}

export interface MaintenanceCommunication {
  enter_visible: boolean;
  enter_enabled: boolean;
  state: string;
  attention: boolean;
  busy: boolean;
  form_enabled: boolean;
  isolation_enabled: boolean;
  /** The declaration as the service's window holds it; shown while a pending write disables the box (D-218). */
  isolated: boolean;
  read_enabled: boolean;
  write_enabled: boolean;
  verify_enabled: boolean;
  pending: boolean;
  form: { serial_port: string; old: CommFields; new: CommFields };
  form_locked: boolean;
  identity: string[];
  target: string;
  fixed_parameters: string;
  baudrates: number[];
  parities: { value: string; label: string }[];
}

export interface MaintenanceFooter {
  resume_visible: boolean;
  resume_enabled: boolean;
  resume_reason: string;
  close_text: string;
  close_enabled: boolean;
  result: string;
  result_error: boolean;
  exported_file: string | null;
}

export interface SettingsCommValue {
  text: string;
  mismatch: boolean;
  tooltip: string;
}

export interface SettingsComm {
  key: string;
  source: string;
  error: boolean;
  tooltip: string;
  /** The values are the last valid read; the latest request did not confirm them (R-1-5; D-219). */
  stale: boolean;
  stale_text: string;
  values: SettingsCommValue[];
}

export interface MaintenanceState {
  available: boolean;
  reason: string;
  version: number;
  session?: boolean;
  tab?: number;
  maintenance?: boolean;
  entering?: boolean;
  halt?: { message: string } | null;
  busy?: boolean;
  devices?: MaintenanceDevice[];
  target?: string;
  target_locked?: boolean;
  header?: { address: string; communication: string; state: string; state_level: string };
  diagnostics?: MaintenanceDiagnostics | null;
  calibration?: MaintenanceCalibration;
  communication?: MaintenanceCommunication;
  footer?: MaintenanceFooter;
  notice?: { title: string; text: string } | null;
  settings?: Record<string, SettingsComm>;
}

/** A write's confirmation (17_ 6.2): V1.0.3's dialog title and text, one id, 60 s, single use. */
export interface WriteConfirmation {
  confirmation_id: string;
  action: string;
  expires_at: string;
  title: string;
  text: string;
}

export type DraftEdit = { field: string; value: number } | { node: number; x: number; y: number };

/* ------------------------------------------------ support (D-226): 导出诊断包 API-27, 维护记录 API-28 */

/** API-27: the zip written into the alpha's output folder; `text` is the page's result line. */
export interface DiagnosticsExported {
  as_of: string;
  path: string;
  directory: string;
  file_name: string;
  size: number;
  files: string[];
  problems: string[];
  text: string;
}

export type MaintenanceLogKind = "calibration_write" | "comm_write" | "comm_verify" | "time_sync";
export type MaintenanceLogResult = "success" | "failure" | "pending";

export interface MaintenanceLogDevice {
  key: string;
  position: number;
  name: string;
  database_name: string;
  state: "ok" | "missing" | "outside" | "unavailable";
  problem: string | null;
}

export interface MaintenanceLogItem {
  device_key: string;
  device_name: string;
  occurred_at: string;
  occurred_at_text: string;
  kind: MaintenanceLogKind;
  kind_text: string;
  before_text: string;
  after_text: string;
  readback_text: string;
  result: MaintenanceLogResult;
  result_text: string;
  detail: string;
  source: string;
}

export interface MaintenanceLogTexts {
  title: string;
  note: string;
  columns: string[];
  empty_text: string;
  no_devices_text: string;
  time_sync_label: string;
  limit_text: string;
  /** shown when scan_limited: older device-log rows were not scanned */
  scan_limited_text: string;
}

/** API-28: every device write the device databases recorded, newest first (read only). */
export interface MaintenanceLog {
  as_of: string;
  devices: MaintenanceLogDevice[];
  items: MaintenanceLogItem[];
  limit: number;
  limit_reached: boolean;
  time_sync: boolean;
  /** only the newest device-log rows of some device were scanned (D-226 问题 4) */
  scan_limited: boolean;
  texts: MaintenanceLogTexts;
}

export interface MaintenanceLogQuery {
  device: string | null;
  timeSync: boolean;
}
