/**
 * The six metric cards of the history page. Same six and order as the V1.0.x overview summary (UI-012: 照度,
 * 350–1050 nm 总辐照度, PPFD, McCree-YPFD, 叶绿素 A / B 加权光子通量), taken by key from the 54 values the
 * service returns (API-06 groups); texts are shown as given.
 */
import type { MetricGroup, MetricItem } from "../api/types";

export const KPI_KEYS = ["lux", "irradiance", "ppfd", "ypfd", "chlorophyll_a_ypfd", "chlorophyll_b_ypfd"] as const;
export const EM_DASH = "—";

export interface Kpi {
  key: string;
  label: string;
  text: string;
  unit: string;
}

export function kpis(groups: MetricGroup[] | null): Kpi[] {
  const byKey = new Map<string, MetricItem>();
  for (const group of groups ?? []) for (const item of group.items) byKey.set(item.key, item);
  return KPI_KEYS.map((key) => {
    const item = byKey.get(key);
    return { key, label: item?.label ?? EM_DASH, text: item?.text ?? EM_DASH, unit: item?.unit ?? "" };
  });
}
