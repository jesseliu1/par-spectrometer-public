/**
 * Chart data of one spectrum as the service sends it (API-06 `spectrum`): x is the wavelength of each point,
 * y the service's `values` unchanged (raw / 10^coefficient is computed by the service, contract 1.2).
 */
import type { ReferenceCurve, ReferenceCurves, Spectrum } from "../api/types";
import { axisNumber } from "./axis";
import { token, tokenNumber } from "./theme";

/** Axis range when no spectrum is shown: the instrument's 350–1050 nm (701 points, 1 nm). */
export const AXIS_START_NM = 350;
export const AXIS_END_NM = 1050;
/** PAR band shaded on the chart, display only (the PAR metric itself is computed by the service, MATH). */
export const PAR_BAND_NM: readonly [number, number] = [400, 700];

export function spectrumSeries(spectrum: Spectrum | null): Array<[number, number]> {
  if (spectrum === null) return [];
  return spectrum.values.map((value, index) => [
    spectrum.wavelength_start + index * spectrum.wavelength_step,
    value,
  ]);
}

export function axisRange(spectrum: Spectrum | null): [number, number] {
  if (spectrum === null || spectrum.values.length === 0) return [AXIS_START_NM, AXIS_END_NM];
  const last = spectrum.wavelength_start + (spectrum.values.length - 1) * spectrum.wavelength_step;
  return [spectrum.wavelength_start, last];
}

/** One coloured segment: x1, y1, x2, y2 and the index of its colour in fill_colors. */
export type FillSegment = [number, number, number, number, number];

/** "#rrggbb" of a service colour ([R, G, B], 0–1). */
export function rgbHex(rgb: readonly number[]): string {
  const hex = rgb.map((value) => Math.round(Math.min(Math.max(value, 0), 1) * 255).toString(16).padStart(2, "0"));
  return `#${hex.join("")}`;
}

/**
 * The V1.0.3 SpectrumCanvas._add_colored_spectrum segments: x_i..x_i+1 takes the colour of x_i (UI-317). A segment
 * with a missing end is left out, so a gap stays a gap.
 */
export function fillSegments(points: ReadonlyArray<readonly [number, number | null]>, reference: ReferenceCurves): FillSegment[] {
  const segments: FillSegment[] = [];
  for (let index = 0; index + 1 < points.length; index += 1) {
    const [x1, y1] = points[index]!;
    const [x2, y2] = points[index + 1]!;
    if (y1 === null || y2 === null) continue;
    segments.push([x1, y1, x2, y2, Math.round(x1 - reference.fill_start)]);
  }
  return segments;
}

/**
 * A matplotlib line width (points) in CSS pixels: V1.0.3's figures keep matplotlib's default 100 dpi, so a width of
 * 1 pt is drawn 100/72 px wide; ECharts takes CSS pixels.
 */
export function matplotlibWidth(points: number): number {
  return (points * 100) / 72;
}

interface RenderApi {
  value(dimension: number): number;
  coord(point: number[]): number[];
}

/** ECharts custom series of the coloured fill and line, each segment filled down to 0 like V1.0.3. */
export function fillSeries(points: ReadonlyArray<readonly [number, number | null]>, reference: ReferenceCurves) {
  const colours = reference.fill_colors.map(rgbHex);
  const width = matplotlibWidth(tokenNumber("--chart-spectrum-segment-width"));
  return {
    type: "custom",
    name: "按波长着色",
    data: fillSegments(points, reference),
    encode: { x: [0, 2], y: [1, 3] },
    silent: true,
    tooltip: { show: false },
    renderItem: (_params: unknown, api: RenderApi) => {
      const [x1, y1, x2, y2] = [api.value(0), api.value(1), api.value(2), api.value(3)];
      const colour = colours[api.value(4)] ?? colours[colours.length - 1];
      const top1 = api.coord([x1, y1]);
      const top2 = api.coord([x2, y2]);
      return {
        type: "group",
        children: [
          {
            type: "polygon",
            shape: { points: [api.coord([x1, 0]), top1, top2, api.coord([x2, 0])] },
            style: { fill: colour, opacity: reference.fill_opacity },
          },
          {
            type: "line",
            shape: { x1: top1[0], y1: top1[1], x2: top2[0], y2: top2[1] },
            style: { stroke: colour, lineWidth: width },
          },
        ],
      };
    },
  };
}

const CURVE_TOKENS: Record<ReferenceCurve["key"], string> = {
  chlorophyll_a: "--chart-ref-chlorophyll-a",
  chlorophyll_b: "--chart-ref-chlorophyll-b",
  mccree: "--chart-ref-mccree",
  photopic: "--chart-ref-photopic",
};
/** matplotlib "-." as an ECharts dash pattern */
const DASH_DOT = [6, 3, 1, 3];

/** The four reference curves on the right axis (yAxisIndex 1), in the V1.0.3 legend order (UI-168). */
export function referenceSeries(reference: ReferenceCurves) {
  return reference.curves.map((curve) => {
    const colour = token(CURVE_TOKENS[curve.key]);
    return {
      type: "line",
      name: curve.label,
      yAxisIndex: 1,
      data: curve.x.map((x, index) => [x, curve.y[index]]),
      symbol: "none", // the legend then shows the line and its dash like V1.0.3, not a point marker
      silent: true,
      lineStyle: { color: colour, width: matplotlibWidth(curve.width), type: curve.line === "dashdot" ? DASH_DOT : curve.line },
      itemStyle: { color: colour },
    };
  });
}

/** The right response axis of the reference curves (V1.0.3: 0 to axis_max, title on the right). */
export function responseAxis(reference: ReferenceCurves, axis: string, grid: string) {
  return {
    type: "value",
    position: "right",
    min: 0,
    max: reference.axis_max,
    name: reference.axis_label,
    nameLocation: "middle",
    nameGap: 40,
    nameTextStyle: { color: axis },
    axisLine: { show: true, lineStyle: { color: axis } },
    axisLabel: { color: axis, showMaxLabel: false, formatter: axisNumber },
    splitLine: { show: false, lineStyle: { color: grid } },
  };
}

/**
 * Legend of the reference curves inside the plot's top left corner as in V1.0.3 (the measured spectrum has no legend
 * entry); `grid` is the chart's grid, so the legend stays below the left axis title.
 */
export function referenceLegend(
  reference: ReferenceCurves,
  grid: { left: number; top: number },
  axis: string,
  fontSize: number,
) {
  const inset = tokenNumber("--space-2");
  return {
    data: reference.curves.map((curve) => curve.label),
    left: grid.left + inset,
    top: grid.top + inset,
    orient: "vertical",
    itemWidth: 24,
    selectedMode: false, // fixed overlay without per-curve switches (UI-168): clicking an entry must not hide its curve
    textStyle: { color: axis, fontSize },
    backgroundColor: token("--color-surface"),
  };
}
