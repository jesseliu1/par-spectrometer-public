/**
 * What the top bar's run status shows (issue #73; UI-253, UI-252): V1.0.3's "总线：… ｜ 采集…" block and its red
 * failure lines. The service words and colours them (GET /acquisition/status `run_status`); this only picks which
 * applies:
 *
 * - a running takeover (also while the tier reads 0 and the takeover is not released, D-215): the service's run status;
 * - tier 1 or 2 without one (未接管 / 正在开始 / 正在停止), or before the status was read: the service's tier text;
 * - tier 0: "未连接设备 / 只读", never 采集运行中 (D-227 item 1);
 * - the tier not read yet: "正在读取状态…" (issue 119: the product acquires by default, so "只读" would be wrong).
 */
import type { AcquisitionStatus, Notice, RunLevel, TierLevel, TierState } from "../api/types";

export const TIER0_TEXT = "未连接设备 / 只读";
export const LOADING_TEXT = "正在读取状态…";

export interface RunView {
  bus: { text: string; level: RunLevel; detail: string; notice?: Notice | null } | null;
  acquisition: { text: string; level: RunLevel | TierLevel; notice?: Notice | null };
  failures: string[];
  /** the record of each failure line (issue 136), same order as `failures` */
  failureNotices: (Notice | null)[];
}

/** "记录号 <id>，出现于 <time>" (issue 136): how a shown message is found again in the diagnostics bundle; "" without one. */
export function noticeText(notice: Notice | null | undefined): string {
  return notice ? `记录号 ${notice.event_id}，出现于 ${notice.occurred_at.replace("T", " ")}` : "";
}

/** `text` with the record line below it, for a tooltip. */
export function withNotice(text: string, notice: Notice | null | undefined): string {
  const line = noticeText(notice);
  return line ? `${text}\n${line}` : text;
}

export function runStatusView(tier: TierState | null, status: AcquisitionStatus | null): RunView {
  const none = { failures: [], failureNotices: [] };
  if (tier === null) return { bus: null, acquisition: { text: LOADING_TEXT, level: "muted" }, ...none };
  if (tier.tier < 1 && tier.takeover === "released") {
    return { bus: null, acquisition: { text: TIER0_TEXT, level: "muted" }, ...none };
  }
  if (tier.takeover === "running" && status !== null && status.takeover === "running") {
    const run = status.run_status;
    const notices = run.failures.map((_, index) => run.failure_notices?.[index] ?? null);
    return { bus: run.bus, acquisition: run.acquisition, failures: run.failures, failureNotices: notices };
  }
  return { bus: null, acquisition: { text: tier.text, level: tier.level }, ...none };
}
