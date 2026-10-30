/**
 * Chart helpers of the DLI page. They only reshape what the service sent; no value is computed here.
 */
import type { DliSeries, DliStateLevel, DliTick } from "../api/types";

/** DliCanvas._layout_plot: charts at least 700 px wide get a tick every 3 h, narrower ones every 6 h (UI-183). */
export const WIDE_CHART_PX = 700;

/** The four charts in V1.0.3 order, with their colour tokens (R-1-5). */
export const METRIC_COLOURS: Record<string, { line: string; fill: string }> = {
  ppfd: { line: "--chart-dli-ppfd", fill: "--chart-dli-ppfd-fill" },
  mccree_ypfd: { line: "--chart-dli-mccree", fill: "--chart-dli-mccree-fill" },
  chlorophyll_a_ypfd: { line: "--chart-dli-chl-a", fill: "--chart-dli-chl-a-fill" },
  chlorophyll_b_ypfd: { line: "--chart-dli-chl-b", fill: "--chart-dli-chl-b-fill" },
};

/** CSS class per state level; the colours are tokens in tokens.css (V1.0.3: grey, amber, green). */
export const STATE_CLASSES: Record<DliStateLevel, string> = { ok: "state-ok", warn: "state-warn", muted: "state-muted" };

export function visibleTicks(ticks: DliTick[], width: number): DliTick[] {
  return width >= WIDE_CHART_PX ? ticks : ticks.filter((tick) => tick.narrow);
}

/** [x, y] pairs of the cumulative curve; a null y breaks the line where the service broke the integration. */
export function curve(series: DliSeries | null): [number, number | null][] {
  if (!series) return [];
  return series.offsets_seconds.map((offset, index) => [offset, series.cumulative[index] ?? null]);
}

/** Tick text by x position (ECharts asks for each custom value). */
export function tickText(ticks: DliTick[], value: number): string {
  return ticks.find((tick) => tick.offset_seconds === value)?.text ?? "";
}

/** Right end of the x axis: the period end, the service's last tick. */
export function axisEnd(ticks: DliTick[]): number {
  return ticks.at(-1)?.offset_seconds ?? 0;
}

/** UI-185: how far the midnight label moves down when it overlaps a neighbour (V1.0.3: 0.26 in at 100 dpi). */
export const STAGGER_PX = 26;

/** Where the staggered midnight label is anchored: "left" when it overlapped the start label, else "right". */
export type MidnightStagger = "left" | "right" | null;

/** Width in px of a tick label as drawn: its longest line. */
export type LabelWidth = (text: string) => number;

/** The midnight tick: the one inner tick whose text carries the date (UI-183, `axis_ticks` of the service). */
export function midnightIndex(ticks: DliTick[]): number {
  return ticks.findIndex((tick, at) => at > 0 && at < ticks.length - 1 && tick.text.includes("\n"));
}

/**
 * UI-185 as in DliCanvas._layout_plot: the midnight label is compared with its left, then its right neighbour among
 * the shown ticks (start label anchored left, end label right, the others centred); on the first overlap it moves
 * down one row, anchored left when that neighbour is the start label, otherwise right. `plotWidth` is the width
 * of the plot area in px; 0 or less (not laid out yet) never staggers.
 */
export function midnightStagger(ticks: DliTick[], plotWidth: number, labelWidth: LabelWidth): MidnightStagger {
  const index = midnightIndex(ticks);
  const end = axisEnd(ticks);
  if (index < 0 || plotWidth <= 0 || end <= 0) return null;
  const box = (at: number): [number, number] => {
    const tick = ticks[at] as DliTick;
    const x = (tick.offset_seconds / end) * plotWidth;
    const width = labelWidth(tick.text);
    if (at === 0) return [x, x + width];
    if (at === ticks.length - 1) return [x - width, x];
    return [x - width / 2, x + width / 2];
  };
  const [left, right] = box(index);
  for (const neighbour of [index - 1, index + 1]) {
    const [from, to] = box(neighbour);
    if (left < to && right > from) return neighbour === 0 ? "left" : "right";
  }
  return null;
}

let measureContext: CanvasRenderingContext2D | null | undefined;

/** ECharts' default label size, used when the font-size token cannot be read. */
const DEFAULT_FONT_PX = 12;

/** Label width with the browser's text metrics; without a canvas (tests) an estimate of 0.6 em per character. */
export function measuredLabelWidth(tokenFontSize: number, fontFamily: string): LabelWidth {
  const fontSize = Number.isFinite(tokenFontSize) && tokenFontSize > 0 ? tokenFontSize : DEFAULT_FONT_PX;
  if (measureContext === undefined) {
    measureContext = typeof document === "undefined" ? null : document.createElement("canvas").getContext("2d");
  }
  const context = measureContext;
  return (text) =>
    Math.max(
      0,
      ...text.split("\n").map((line) => {
        if (!context) return line.length * fontSize * 0.6;
        context.font = `${fontSize}px ${fontFamily}`;
        return context.measureText(line).width;
      }),
    );
}

const AS_OF = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.(\d{1,3}))?/;

/** Latest date the picker offers (API-10 refuses only days after today): the Beijing day of the service's `as_of`
 * moved on by the time elapsed since that answer arrived. A finished period is not reloaded, so `as_of` alone would
 * keep yesterday as the limit after midnight (review of PR #47, M-1). The browser's date and time zone are never
 * read; only an elapsed interval, never negative. */
export function latestDate(asOf: string, elapsedMs: number): string {
  const match = AS_OF.exec(asOf);
  if (!match) return asOf.slice(0, 10);
  const [year = 0, month = 1, day = 1, hour = 0, minute = 0, second = 0] = match.slice(1, 7).map(Number);
  const millis = Number((match[7] ?? "0").padEnd(3, "0"));
  const wall = Date.UTC(year, month - 1, day, hour, minute, second, millis) + Math.max(0, elapsedMs);
  return new Date(wall).toISOString().slice(0, 10);
}
