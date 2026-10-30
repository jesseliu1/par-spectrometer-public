/**
 * Query times of the history page (UI-047, UI-049, UI-050).
 *
 * The service compares times as stored text, Beijing time, exactly YYYY-MM-DDTHH:MM:SS.mmm. Like V1.0.x
 * (ui.py _build_history), the start of an applied range ends in .000 and the end in .999, at whole seconds.
 * "Now" is never the browser's clock: it is the service's `as_of` (Beijing time through the Clock interface), so
 * a PC set to another time zone still gets Beijing times.
 */

export const EARLIEST_QUERY = "0001-01-01T00:00:00.000";
export const LATEST_QUERY = "9999-12-31T23:59:59.999";
const INPUT = /^(\d{4}-\d{2}-\d{2})T(\d{2}:\d{2})(:\d{2})?(?:\.\d{1,3})?$/;
const DATE = /^\d{4}-\d{2}-\d{2}/;

export interface RangeInput {
  /** datetime-local values, YYYY-MM-DDTHH:MM:SS */
  start: string;
  end: string;
}

export interface QueryRange {
  start: string;
  end: string;
}

export class RangeInputError extends Error {
  constructor(readonly field: "start" | "end") {
    super(field === "start" ? "开始时间格式不正确" : "结束时间格式不正确");
    this.name = "RangeInputError";
  }
}

/** A datetime-local value (seconds optional, as browsers drop ":00") as YYYY-MM-DDTHH:MM:SS, or null. */
export function wholeSeconds(value: string): string | null {
  const match = INPUT.exec(value.trim());
  if (!match) return null;
  return `${match[1]}T${match[2]}${match[3] ?? ":00"}`;
}

/** The range sent to API-05: start at .000 and end at .999, as V1.0.x applies the edited range. */
export function toQueryRange(input: RangeInput): QueryRange {
  const start = wholeSeconds(input.start);
  if (start === null) throw new RangeInputError("start");
  const end = wholeSeconds(input.end);
  if (end === null) throw new RangeInputError("end");
  return { start: `${start}.000`, end: `${end}.999` };
}

/**
 * UI-049 default range: from 00:00 of the day of the oldest of the newest 500 records (none: the day of `asOf`)
 * to `asOf` at whole seconds. Like V1.0.x, the stored date is taken as written (a legacy "+00:00" record keeps
 * its own date).
 */
export function defaultRange(asOf: string, oldestOfNewest: string | null): RangeInput {
  const day = oldestOfNewest !== null && DATE.test(oldestOfNewest) ? oldestOfNewest : asOf;
  return { start: `${day.slice(0, 10)}T00:00:00`, end: asOf.slice(0, 19) };
}
