/**
 * Which page is shown. Kept in the address as ?view=… so a reload (and the screenshot tool) opens the same page;
 * the token fragment is handled separately by api/client.ts.
 */
export type PageKey = "overview" | "history" | "calc" | "dli" | "settings" | "maintenance";

export interface PageTag {
  text: string;
  tooltip: string;
}

/** Issue #82: no page shows imported snapshots; without a registered device the pages are empty and say so. */
export const NO_DEVICE_TEXT =
  "还没有设备数据：开启采集模式，在“设置与导出”页登记设备并开始采集后，这里显示本软件采集的数据。";

/** `tier`: the page is offered from this device-write tier on (设备维护: tier 2, 17_ section 2). */
export const PAGES: { key: PageKey; label: string; tag?: PageTag; tier?: number }[] = [
  { key: "overview", label: "实时概览" },
  { key: "history", label: "历史回放" },
  { key: "calc", label: "光谱计算" },
  { key: "dli", label: "光积累计算" },
  { key: "settings", label: "设置与导出" },
  { key: "maintenance", label: "设备维护", tier: 2 },
];

const VIEW_PARAM = "view";

export function viewFrom(search: string): PageKey {
  const value = new URLSearchParams(search).get(VIEW_PARAM);
  return PAGES.some((page) => page.key === value) ? (value as PageKey) : "history";
}

/** The address search part for `view` (other parameters kept; history is the default and needs none). */
export function searchFor(search: string, view: PageKey): string {
  const params = new URLSearchParams(search);
  if (view === "history") params.delete(VIEW_PARAM);
  else params.set(VIEW_PARAM, view);
  const text = params.toString();
  return text ? `?${text}` : "";
}

/** The service time as the status line shows it: "YYYY-MM-DD HH:MM:SS", no "T" and no milliseconds (alpha.5). */
export function serviceTime(asOf: string): string {
  return asOf.replace("T", " ").slice(0, 19);
}

/** The live device button's position: "1".."4" for p1..p4 (alpha.5: no "p" shown). */
export function positionNumber(key: string): string {
  return key.replace(/^p/, "");
}
