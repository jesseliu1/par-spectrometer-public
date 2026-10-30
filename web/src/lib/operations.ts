/**
 * Chart data of the spectrum calculation page as the service sends it (API-14): x is the wavelength of each of the
 * 701 points, y the service's value unchanged; null stays null, so the chart breaks there instead of drawing zero
 * (UI-218). The tick set follows the chart's width (UI-192); both sets and the width come from the service.
 */
import type { OperationAxis } from "../api/types";

export function chartPoints(values: (number | null)[] | null, startNm: number): Array<[number, number | null]> {
  if (values === null) return [];
  return values.map((value, index) => [startNm + index, value]);
}

export function ticksFor(axis: OperationAxis, widthPx: number): number[] {
  return widthPx > 0 && widthPx < axis.narrow_below_px ? axis.ticks_narrow : axis.ticks_wide;
}

/** Whether an axis end is a "round" value worth a label (at most three decimals). */
export function isRound(value: number): boolean {
  const scaled = value * 1000;
  return Math.abs(scaled - Math.round(scaled)) < 1e-6;
}
