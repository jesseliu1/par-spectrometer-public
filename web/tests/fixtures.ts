import type {
  AcquisitionDetail,
  AcquisitionExported,
  DeviceLog,
  DeviceSummary,
  ExportCount,
  ExportKind,
  SettingsView,
  DeviceList,
  DliDay,
  DliMetric,
  Health,
  HistoryItem,
  HistoryPage,
  OperationCandidate,
  OperationCandidates,
  OperationComputation,
  OperationInput,
  OperationInputs,
  OperationKey,
  OperationPage,
  OperationSources,
  Overview,
  SnapshotList,
  SourceRef,
  ReferenceCurves,
} from "../src/api/types";

export const AS_OF = "2026-10-18T09:30:15.123";

export function health(): Health {
  return { status: "ok", version: "2.0.0-alpha.9", build_commit: null, tier: 0, started_at: AS_OF };
}

/** The devices of the alpha's own configuration (issue #82): `configured` positions hold a device database. */
export function devices(configured: string[] = ["p1"], ids: Record<string, string> = {}): DeviceList {
  return {
    as_of: AS_OF,
    source: "live_ro",
    tier: 0,
    items: [1, 2, 3, 4].map((position) => {
      const key = `p${position}`;
      const on = configured.includes(key);
      return {
        key,
        position,
        configured: on,
        enabled: on,
        name: on ? `设备${position}` : "",
        address_text: null,
        display_state: on ? "normal" : "unconfigured",
        database_name: on ? `${key}.sqlite3` : null,
        database_path: on ? `/alpha/data/devices/${key}.sqlite3` : null,
        snapshot_id: on ? (ids[key] ?? `${key}-db`) : null,
        imported_at: null,
      };
    }),
  };
}

export function snapshots(): SnapshotList {
  return { as_of: AS_OF, source: "snapshot", items: [] };
}

export function item(id: number, acquiredAt: string, success = true, seq = 1): HistoryItem {
  return {
    seq,
    id,
    acquired_at: acquiredAt,
    acquired_at_text: acquiredAt.replace("T", " "),
    success,
    result_text: success ? "成功" : "失败",
    exposure_status: success ? 0 : null,
    exposure_text: success ? "正常" : "未知",
    exposure_style: success ? "normal" : "warn",
  };
}

export function page(items: HistoryItem[], range = { start: "x", end: "y" }, limitReached = false): HistoryPage {
  return {
    as_of: AS_OF,
    source: "snapshot",
    snapshot_id: "p1-snap",
    range,
    limit: 500,
    offset: 0,
    limit_reached: limitReached,
    next_offset: null,
    items: items.map((entry, index) => ({ ...entry, seq: index + 1 })),
  };
}

export function detail(id: number, key = "p1", success = true): AcquisitionDetail {
  const text = (value: string) => (success ? value : "—");
  return {
    as_of: AS_OF,
    source: "snapshot",
    snapshot_id: `${key}-snap`,
    device: { key, name: "设备1" },
    header: {
      title: `记录详情 · 设备1 · #${id}`,
      time_text: "2026-10-18 09:00:00.000（北京时间）",
      status_text: success ? "采集成功 · 单次读取完成" : "采集失败",
      status_level: success ? "ok" : "error",
      exposure_text: "正常",
    },
    success,
    elapsed_text: "5464.7",
    review_text: "单次读取完成",
    groups: [
      {
        title: "常用光量",
        items: [
          { key: "lux", label: "照度", unit: "lx", text: text("1234.5") },
          { key: "irradiance", label: "350–1050 nm 总辐照度", unit: "W/m²", text: text("12.345") },
          { key: "ppfd", label: "PPFD", unit: "μmol·m⁻²·s⁻¹", text: text("56.789") },
          { key: "ypfd", label: "McCree-YPFD", unit: "μmol·m⁻²·s⁻¹", text: text("45.6") },
          { key: "chlorophyll_a_ypfd", label: "叶绿素 A 加权光子通量", unit: "μmol·m⁻²·s⁻¹", text: text("11.1") },
        ],
      },
    ],
    record: { id, acquired_at: "2026-10-18T09:00:00.000" },
    spectrum_state: success ? "ok" : "none",
    spectrum: success
      ? { wavelength_start: 350, wavelength_step: 1, spectral_coefficient: 3, points: [1000, 2000, 3000], values: [1, 2, 3] }
      : null,
  };
}

export function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

export function errorBody(code: string, message: string, retryable: boolean) {
  return { error: { code, message, retryable, detail: null } };
}

export function dliMetric(key: string, title: string, covered = true): DliMetric {
  return {
    key,
    title,
    summary: {
      total: covered ? 2.408 : 0,
      covered_seconds: covered ? 1740 : 0,
      missing_seconds: covered ? 9269 : 11009,
      coverage: covered ? 0.158 : 0,
      first_valid: covered ? "2026-10-18T07:00:00.000" : null,
      last_valid: covered ? "2026-10-18T07:29:00.000" : null,
      integrated_until: covered ? "2026-10-18T07:29:00.000" : null,
      head_seconds: 2010,
      internal_seconds: 0,
      tail_seconds: covered ? 7260 : 0,
      cutoff: "2026-10-18T09:30:00.000",
      state: covered ? "部分累计" : "有效数据不足",
      stale: covered,
      paused: false,
    },
    header: {
      total_text: covered ? "已累计：2.408 mol·m⁻²" : "已累计：— mol·m⁻²",
      state_text: covered ? "部分累计 · 数据未更新（2时01分00秒）" : "有效数据不足",
      state_level: covered ? "warn" : "muted",
      times_text: covered ? "首个有效：10-18 07:00:00　累计截至：10-18 07:29:00" : "首个有效：—　累计截至：—",
      coverage_text: covered ? "有效 0时29分00秒　未覆盖 2时34分29秒　覆盖率 15.8%" : "有效 0时00分00秒",
      coverage_tooltip: "截至 2026-10-18 09:30:00（北京时间）\n起始未覆盖：0时33分30秒",
    },
    y_max: covered ? 2.769 : 0.001,
    series: covered
      ? {
          times: ["2026-10-18T07:00:00.000", "2026-10-18T07:10:30.000", "2026-10-18T07:11:00.000"],
          offsets_seconds: [2010, 2640, 2670],
          cumulative: [0, null, 1.2],
        }
      : { times: [], offsets_seconds: [], cumulative: [] },
  };
}

export function dliDay(key = "p1", date = "2026-10-18", current = true): DliDay {
  return {
    as_of: AS_OF,
    source: "snapshot",
    snapshot_id: `${key}-snap`,
    device: { key, name: "设备1" },
    requested_date: current ? null : date,
    period: {
      start: `${date}T06:26:30.005`,
      end: "2026-10-19T06:26:30.005",
      date,
      current,
      text: `积分周期：${date} 06:26 → 2026-10-19 06:26（北京时间，日出起算，固定24小时）`,
    },
    location: {
      latitude: 39.9042,
      longitude: 116.4074,
      stored: false,
      coordinates_text: "纬度 39.9042 °N，经度 116.4074 °E",
      text: "已保存位置：纬度 39.9042 °N，经度 116.4074 °E\nDLI启用时间：2026-10-01 00:00:00.000",
    },
    enabled: { at: "2026-10-01T00:00:00.000", stored: true, text: "2026-10-01 00:00:00.000" },
    observed_until: "2026-10-18T09:30:00.000",
    poll_cycle_seconds: 300,
    poll_cycle_source: "record",
    poll_cycle_record_at: "2026-10-18T09:25:00.000",
    max_gap_seconds: 360,
    gap_text: "允许间隔 360 秒（按轮询周期 300 秒计，取自 2026-10-18 09:25:00.000 的采集记录）",
    snapshot_text: "数据来自快照（导入于 2026-10-18T09:00:00.000），导入之后的采集不在其中",
    paused: false,
    metrics: [
      dliMetric("ppfd", "PPFD-DLI（400–700 nm）"),
      dliMetric("mccree_ypfd", "McCree YPFD-DLI"),
      dliMetric("chlorophyll_a_ypfd", "叶绿素 A 加权日光积分"),
      dliMetric("chlorophyll_b_ypfd", "叶绿素 B 加权日光积分", false),
    ],
    interruptions: [
      { occurred_at: "2026-10-18T07:10:30.000", occurred_at_text: "2026-10-18 07:10:30.000", reason: "恢复命令未确认" },
    ],
    ticks: [
      { offset_seconds: 0, at: `${date}T06:26:30.005`, text: "10-18\n06:26", narrow: true },
      { offset_seconds: 9210, at: `${date}T09:00:00.000`, text: "09:00", narrow: false },
      { offset_seconds: 20010, at: `${date}T12:00:00.000`, text: "12:00", narrow: true },
      { offset_seconds: 63210, at: "2026-10-19T00:00:00.000", text: "10-19\n00:00", narrow: true },
      { offset_seconds: 86400, at: "2026-10-19T06:26:30.005", text: "10-19\n06:26", narrow: true },
    ],
  };
}

/* --- 光谱计算 ---------------------------------------------------------------------------------------------- */

export function operationPage(): OperationPage {
  const paragraph = (head: string | null, text: string) => ({ head, text });
  return {
    as_of: AS_OF,
    source: "snapshot",
    title: "光谱计算",
    operations: [
      { key: "add", label: "加法 A+B" },
      { key: "subtract", label: "减法 A-B" },
      { key: "divide", label: "比值 A/B" },
    ],
    default_operation: "add",
    texts: {
      source_labels: ["A", "B"],
      operation_label: "算法",
      run_label: "执行计算",
      export_label: "导出计算结果",
      swap_tooltip: "交换光谱 A 与 B",
      auto_match_label: "B 匹配 A 的最近时间",
      auto_match_tooltip: "最近不代表同步",
      time_tooltip: "最近时间匹配不是同步采集。",
      no_spectrum: "无可用光谱",
      input_empty_heading: "暂无可显示的光谱",
      input_empty_detail: "选择有效采集记录后将在此显示曲线",
      waiting_heading: "等待执行计算",
      missing_heading: "缺少有效的 A/B 光谱",
      missing_detail: "A、B 均需成功且完整的光谱记录",
      result_title: "计算结果",
      x_label: "波长 (nm)",
      power_y_label: "功率 (mW/nm)",
      empty_sources: "尚未导入历史库快照",
    },
    axis: {
      start_nm: 350,
      end_nm: 1050,
      ticks_wide: [350, 400, 500, 600, 700, 800, 900, 1000, 1050],
      ticks_narrow: [350, 500, 600, 700, 800, 900, 1050],
      narrow_below_px: 680,
    },
    guide: {
      title: "光谱计算应用说明",
      details_button: "查看完整说明…",
      close_button: "关闭",
      summary: [paragraph("加法 A+B · 补光组合：", "同点测量两盏灯。"), paragraph("比值 A/B · 叶片：", "不代表吸收率。")],
      navigation: [
        { text: "补光", anchor: "lighting" },
        { text: "显示与导出", anchor: "display" },
      ],
      intro: "本页对已选光谱逐波长执行。",
      sections: [
        { anchor: "lighting", title: "1. 加法", paragraphs: [paragraph("来源与用途：", "两盏灯。")], links: [] },
        {
          anchor: null,
          title: "参考资料",
          paragraphs: [paragraph(null, "以下为参考。")],
          links: [{ text: "RP Photonics：Transmittance", url: "https://www.rp-photonics.com/transmittance.html" }],
        },
      ],
      dialog: { width_px: 960, height_px: 760, screen_fraction: 0.9 },
    },
    export: {
      title: "导出计算结果",
      formats_label: "导出格式",
      formats: [
        { key: "csv", label: "CSV", checked: true },
        { key: "xlsx", label: "Excel (.xlsx)", checked: false },
      ],
      cancel_label: "取消",
      confirm_label: "导出到输出目录",
      note: "本软件不弹出目录选择框",
      done_title: "导出完成",
      failed_title: "导出失败",
      directory: "/alpha/exports",
    },
  };
}

export function operationSources(keys: string[] = ["p1", "p2"]): OperationSources {
  return {
    as_of: AS_OF,
    source: "snapshot",
    items: keys.map((key) => ({
      key,
      position: Number(key.slice(1)),
      device_name: `设备${key.slice(1)}`,
      snapshot_id: `${key}-snap`,
      database_path: `/alpha/data/imported/${key}.sqlite`,
      source_path: `/v1/${key}.sqlite3`,
      imported_at: AS_OF,
      display_state: "normal",
      tooltip: `源库：/v1/${key}.sqlite3`,
    })),
    initial_a: keys[0] ?? null,
    initial_b: keys[Math.min(1, keys.length - 1)] ?? null,
  };
}

export function candidate(id: number, acquiredAt: string): OperationCandidate {
  return { id, acquired_at: acquiredAt, acquired_at_text: acquiredAt.replace("T", " "), label: `#${id} | ${acquiredAt}` };
}

export function candidates(key: string, items: OperationCandidate[], snapshot = `${key}-snap`): OperationCandidates {
  return { as_of: AS_OF, source: "snapshot", key, snapshot_id: snapshot, limit: 500, items, empty_text: "无可用光谱" };
}

function input(label: string, ref: SourceRef | null): OperationInput {
  const valid = ref !== null && ref.id > 0;
  return {
    label,
    source: ref?.source ?? null,
    snapshot_id: ref?.snapshot_id ?? null,
    id: ref?.id ?? null,
    valid,
    title: valid ? `光谱 ${label}：设备 · #${ref?.id}` : `光谱 ${label}：未选择记录`,
    legend: `光谱 ${label}`,
    device_name: valid ? "设备" : null,
    acquired_at: valid ? "2026-10-18T08:00:00.000" : null,
    acquired_at_text: valid ? "2026-10-18 08:00:00.000" : null,
    y_range: valid ? [0, 3] : null,
    values: valid ? [1, 2, 3] : null,
  };
}

export function operationInputs(a: SourceRef | null, b: SourceRef | null): OperationInputs {
  const shownA = input("A", a);
  const shownB = input("B", b);
  const valid = shownA.valid && shownB.valid;
  return {
    as_of: AS_OF,
    source: "snapshot",
    a: shownA,
    b: shownB,
    valid,
    time_difference: { seconds: valid ? 60 : null, text: valid ? "采集时间差：B 比 A 晚 60.000 秒" : "采集时间差：不可用", tooltip: "t" },
    placeholder: valid
      ? { heading: "等待执行计算", detail: "" }
      : { heading: "缺少有效的 A/B 光谱", detail: "A、B 均需成功且完整的光谱记录" },
  };
}

export function computation(a: SourceRef, b: SourceRef, operation: OperationKey): OperationComputation {
  const ratio = operation === "divide";
  return {
    ...operationInputs(a, b),
    result: {
      operation,
      operation_label: operation,
      title: `计算结果：${operation}`,
      legend: "计算结果",
      y_label: ratio ? "比值（A/B）" : "功率 (mW/nm)",
      ratio,
      values: [0.5, 1, null],
      plotted: ratio ? [0.5, null, null] : [0.5, 1, null],
      y_range: ratio ? [0, 1.5] : [0, 2],
      reference_line: ratio,
      ratio_note: ratio ? "比值显示：A、B 均达到两条光谱最大峰值的 2%。" : null,
      empty_text: null,
      threshold: ratio ? 0.04 : null,
    },
  };
}

/* ---- settings page (API-26, API-15, API-22, API-23) ---- */

export const NO_CONFIG = "只读快照不含配置";

export function settingsView(configured: string[] = ["p1", "p2"]): SettingsView {
  return {
    as_of: AS_OF,
    source: "snapshot",
    tier: 0,
    title: "设置与导出",
    groups: ["通信设置", "设备登记", "采集记录导出", "设备状态与最近日志"],
    read_only_text: "alpha 只读（档位 0）：不连接、不写设备，不保存、不应用配置；保存配置、设备维护和通信参数读写未开放。",
    config_text: NO_CONFIG,
    config_note: "总线参数和设备登记保存在 V1.0.x 的配置文件里（D-209）。",
    bus: ["连接方式", "计算机串口", "波特率", "奇偶校验", "TCP 主机", "TCP 端口", "全总线轮询周期"].map((label) => ({
      label,
      text: NO_CONFIG,
    })),
    device_columns: ["设备名称", "从站地址", "启用采集", "失败停止", "数据库文件"],
    devices: [1, 2, 3, 4].map((position) => {
      const key = `p${position}`;
      const on = configured.includes(key);
      return {
        key,
        position,
        configured: on,
        state_text: on ? null : "未配置",
        name: on ? `设备${position}` : "",
        slave_id_text: on ? NO_CONFIG : null,
        enabled_text: on ? NO_CONFIG : null,
        fail_stop_text: on ? NO_CONFIG : null,
        database_name: on ? `${key}.sqlite3` : null,
        database_path: on ? `C:\\PAR\\data\\${key}.sqlite3` : null,
        snapshot_path: on ? `/alpha/data/imported/${key}.sqlite` : null,
        snapshot_id: on ? `${key}-snap` : null,
        imported_at: on ? AS_OF : null,
        tooltip: on ? `源库：C:\\PAR\\data\\${key}.sqlite3\n快照：/alpha/data/imported/${key}.sqlite（导入于 ${AS_OF}）` : null,
      };
    }),
    export: {
      title: "采集记录导出",
      device_label: "导出设备",
      range_label: "导出范围",
      start_label: "开始时间",
      end_label: "结束时间",
      count_label: "预计记录数",
      content_label: "内容",
      formats_label: "导出格式",
      ranges: [
        ...[1, 2, 4, 8, 24].map((hours) => ({ key: `${hours}h`, label: `最近 ${hours} 小时` })),
        { key: "custom", label: "自定义时间" },
      ],
      default_range: "1h",
      formats: [
        { key: "csv", label: "CSV", checked: true },
        { key: "xlsx", label: "Excel (.xlsx)", checked: false },
      ],
      content_note: "每条记录一个文件，包含指标与 701 点原始光谱。",
      content_tooltip: "包含状态、软件指标和硬件光度参数；按设备、格式、采集日期分目录存放。",
      button_label: "导出采集记录",
      counting_text: "正在统计记录数…",
      no_device_text: "尚未配置导出设备",
      done_title: "导出",
      failed_title: "导出失败",
      directory: "/alpha/exports",
      note: "本软件不弹出目录选择框：文件写到下面的输出目录。",
    },
  };
}

export function deviceSummary(key = "p1"): DeviceSummary {
  return {
    as_of: AS_OF,
    source: "snapshot",
    snapshot_id: `${key}-snap`,
    device: { key, name: `设备${key.slice(1)}` },
    total: 12,
    latest: "2026-10-18T09:00:00.000",
    records_text: "最近采集：2026-10-18 09:00:00.000 · 共 12 条",
    database_name: `${key}.sqlite3`,
    database_size_text: "0.05 MB",
    database_text: `数据库：${key}.sqlite3 · 文件大小：0.05 MB（导入时）`,
    serial_text: "设备序列号：0x1234ABCD",
    status_text: `设备${key.slice(1)} · 只读快照（导入于 ${AS_OF}），未连接设备`,
    poll_cycle_text: "300 秒（取自 2026-10-18 09:00:00.000 的采集记录）",
  };
}

/** API-16 of a tier-1 device: the status line and two log rows, the newer one a WARNING (shown in red). */
export function deviceLog(key = "p1", status = "在线 · 采集正常 · 曝光：正常"): DeviceLog {
  const name = `设备${key.slice(1)}`;
  const row = (id: number, time: string, level: string, category: string, categoryText: string, message: string) => ({
    id,
    occurred_at: `2026-10-18T${time}.000`,
    time_text: `2026-10-18 ${time}.000`,
    level,
    category,
    category_text: categoryText,
    category_tooltip: `${categoryText}\n${category}`,
    message,
    result_text: message,
    result_tooltip: message,
    details: "{}",
    error: level === "WARNING",
    details_text: `设备：${name}\n数据库：/alpha/data/devices/${key}.sqlite3\n时间：2026-10-18 ${time}.000\n级别：${level}\n类别：${categoryText}（${category}）\n\n消息：\n${message}\n\n详情：\n{}`,
  });
  return {
    as_of: AS_OF,
    source: "live_ro",
    snapshot_id: `${key}-snap`,
    device: { key, name },
    status: { text: `${name} · ${status}`, level: "ok", tone: "normal", tooltip: `${name}\n设备序列号：0x1234ABCD` },
    columns: ["时间", "类别", "结果"],
    details_title: "日志详情",
    copy_label: "复制全部",
    items: [
      row(2, "09:01:00", "WARNING", "communication", "通信异常", "设备无应答"),
      row(1, "09:00:00", "INFO", "connection", "连接", "总线已连接"),
    ],
  };
}

export interface CountArgs {
  key: string;
  range: string;
  start?: string;
  end?: string;
  formats: ExportKind[];
  count?: number;
  notice?: string | null;
  now?: string;
}

/** What the service answers for a count: presets end at `now` (the service clock), custom ranges as given. */
export function exportCount(args: CountArgs): ExportCount {
  const now = args.now ?? "2026-10-18T09:30:00";
  const hours = Number.parseInt(args.range, 10);
  const preset = args.range !== "custom";
  const end = preset ? now : (args.end ?? "");
  const start = preset ? shiftHours(now, -hours) : (args.start ?? "");
  const count = args.count ?? 3;
  const files = count * args.formats.length;
  const name = `设备${args.key.slice(1)}`;
  const notice = args.notice ?? null;
  return {
    as_of: AS_OF,
    source: "snapshot",
    snapshot_id: `${args.key}-snap`,
    device: { key: args.key, name },
    range: { mode: args.range, start, end, start_text: start.replace("T", " "), end_text: end.replace("T", " "), editable: !preset },
    formats: args.formats,
    count,
    files,
    text: `预计 ${count} 条记录，将导出为 ${files} 个文件`,
    can_export: count > 0 && args.formats.length > 0,
    confirm:
      count > 0 && args.formats.length > 0 && notice === null
        ? { title: "确认导出", text: `导出设备：${name}\n时间范围：${start} 至 ${end}\n是否继续？`, records: count, files }
        : null,
    notice,
  };
}

function shiftHours(at: string, hours: number): string {
  const moment = new Date(`${at}Z`);
  moment.setUTCHours(moment.getUTCHours() + hours);
  return moment.toISOString().slice(0, 19);
}

export function exported(files = 3): AcquisitionExported {
  return {
    as_of: AS_OF,
    directory: "/alpha/exports",
    device_folder: "设备1",
    records: files,
    files,
    text: `已导出 ${files} 个文件到：\n/alpha/exports`,
  };
}

/** API-09 overview of `key` showing record `id` (null: nothing shown), as the service answers it. */
export function overview(key = "p1", id: number | null = 7, options: { failedRound?: boolean; metricsError?: boolean } = {}): Overview {
  const shown = id !== null;
  const kpi = (k: string, title: string, text: string) => ({ key: k, title, text: shown ? text : "—" });
  return {
    as_of: AS_OF,
    source: "snapshot",
    snapshot_id: `${key}-snap`,
    device: { key, name: `设备${key.slice(1)}` },
    snapshot_text: "快照数据，非实时：导入于 2026-10-18 09:00:00.000，导入之后的采集不在其中；“距今”按本机当前时间计算",
    texts: {
      page_title: "实时概览",
      summary_title: "实时摘要",
      summary_context: "当前设备的最近一条有效采集记录",
      details_button: "全部指标",
      metrics_toggle: "显示指标",
      spectrum_title: "最新光谱",
      x_label: "波长 (nm)",
      y_label: "功率 (mW/nm)",
      empty_heading: "暂无可显示的光谱",
      empty_detail: "选择有效采集记录后将在此显示曲线",
      invalid_spectrum: "光谱数据无法解析",
      details_columns: ["指标", "数值", "单位"],
      details_close: "关闭",
    },
    display_record: shown
      ? {
          id,
          acquired_at: "2026-10-18T09:29:00.000",
          acquired_at_text: "2026-10-18 09:29:00.000",
          age_seconds: 75.123,
          age_text: "距今 75 秒",
          exposure_text: "正常",
          elapsed_text: "5464.7",
          review_text: "单次读取完成",
          details_title: `全部指标 · #${id} · 2026-10-18 09:29:00.000`,
        }
      : null,
    latest_attempt: shown
      ? {
          id: options.failedRound ? id + 1 : id,
          success: !options.failedRound,
          acquired_at: "2026-10-18T09:29:00.000",
          acquired_at_text: "2026-10-18 09:29:00.000",
        }
      : null,
    status: shown
      ? {
          text: `● ${options.failedRound ? "本轮失败 · 保留最近有效数据" : "采集成功"} · 单次读取完成　显示 #${id}　2026-10-18 09:29:00.000　距今 75 秒　曝光：正常　耗时：5464.7 ms`,
          level: options.failedRound ? "error" : "ok",
        }
      : { text: "", level: "none" },
    stale: shown ? false : null,
    stale_after_seconds: 120,
    poll_cycle_seconds: 60,
    poll_cycle_source: "default",
    poll_cycle_text: "超过 120 秒无新记录时提示“暂无新记录”",
    kpis: [
      kpi("lux", "照度", "1234.5 lx"),
      kpi("irradiance", "350–1050 nm 总辐照度", "701.000 W/m²"),
      kpi("ppfd", "PPFD", options.metricsError ? "—" : "1386.081 µmol·m⁻²·s⁻¹"),
      kpi("ypfd", "McCree-YPFD", options.metricsError ? "—" : "1100.000 µmol·m⁻²·s⁻¹"),
      kpi("chlorophyll_a_ypfd", "叶绿素 A 加权光子通量", options.metricsError ? "—" : "500.000 µmol·m⁻²·s⁻¹"),
      kpi("chlorophyll_b_ypfd", "叶绿素 B 加权光子通量", options.metricsError ? "—" : "400.000 µmol·m⁻²·s⁻¹"),
    ],
    core_metrics: [],
    table: [],
    chart: {
      title: shown && !options.metricsError ? "最新光谱" : "当前设备暂无可显示光谱",
      spectrum_state: shown && !options.metricsError ? "ok" : "none",
      spectrum:
        shown && !options.metricsError
          ? { wavelength_start: 350, wavelength_step: 1, spectral_coefficient: 3, points: [1000, 2000], values: [1, 2] }
          : null,
      y_max: shown && !options.metricsError ? 2 / 0.618 : null,
      x_ticks: [350, 400, 500, 600, 700, 800, 900, 1000, 1050],
      overlay:
        shown && !options.metricsError
          ? [
              [{ label: "PAR 波段辐照度（W/m²）", text: "301.000" }],
              [{ label: "蓝红光子比 B:R", text: "0.833" }, { label: "一般显色指数 Ra", text: "—" }],
            ]
          : [],
    },
    details_enabled: shown,
    metrics_error: options.metricsError
      ? { message: `记录 #${id} 的指标数据无法解析，指标只显示到出错之前`, detail: "TypeError: bad" }
      : null,
  };
}

/** API-08 with short curves; fill colours: 350 nm red, 351 nm blue, 352 nm green, the rest grey. */
export function referenceCurves(): ReferenceCurves {
  const curve = (key: ReferenceCurves["curves"][number]["key"], label: string, line: "dashed" | "dotted" | "dashdot") => ({
    key,
    label,
    line,
    width: 1.6,
    x: [400, 401],
    y: [0.5, 1],
  });
  return {
    curves: [
      curve("chlorophyll_a", "叶绿素 A", "dashed"),
      curve("chlorophyll_b", "叶绿素 B", "dotted"),
      curve("mccree", "McCree 相对作用曲线（参考）", "dashdot"),
      curve("photopic", "人眼明视觉响应 V(λ，虚线)", "dashed"),
    ],
    axis_label: "归一化响应（叶绿素 / McCree）",
    axis_max: 1.5,
    fill_start: 350,
    fill_colors: [[1, 0, 0], [0, 0, 1], [0, 1, 0], ...Array.from({ length: 698 }, () => [0.55, 0.55, 0.55])],
    fill_opacity: 0.55,
  };
}
