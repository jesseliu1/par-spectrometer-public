import { describe, expect, it } from "vitest";
import { defaultRange, RangeInputError, toQueryRange, wholeSeconds } from "../src/lib/timeRange";

describe("time range", () => {
  it("applies an edited range as .000 / .999 at whole seconds, like V1.0.x", () => {
    expect(toQueryRange({ start: "2026-10-18T00:00:00", end: "2026-10-18T09:30:15" })).toEqual({
      start: "2026-10-18T00:00:00.000",
      end: "2026-10-18T09:30:15.999",
    });
  });

  it("accepts the browser dropping ':00' seconds and ignores fractions", () => {
    expect(wholeSeconds("2026-10-18T09:30")).toBe("2026-10-18T09:30:00");
    expect(wholeSeconds("2026-10-18T09:30:15.5")).toBe("2026-10-18T09:30:15");
    expect(wholeSeconds("18/10/2026")).toBeNull();
  });

  it("names the field that cannot be read", () => {
    expect(() => toQueryRange({ start: "", end: "2026-10-18T09:30:15" })).toThrow(RangeInputError);
    try {
      toQueryRange({ start: "2026-10-18T00:00:00", end: "bad" });
    } catch (error) {
      expect((error as RangeInputError).field).toBe("end");
    }
  });

  it("UI-049: default range from the oldest of the newest records' day to the service time", () => {
    expect(defaultRange("2026-10-18T09:30:15.123", "2026-10-16T22:10:00.000")).toEqual({
      start: "2026-10-16T00:00:00",
      end: "2026-10-18T09:30:15",
    });
  });

  it("UI-049: with no records the start is today 00:00 of the service clock", () => {
    expect(defaultRange("2026-10-18T09:30:15.123", null)).toEqual({
      start: "2026-10-18T00:00:00",
      end: "2026-10-18T09:30:15",
    });
  });

  it("takes a legacy '+00:00' time's own date, as V1.0.x does", () => {
    expect(defaultRange("2026-10-18T09:30:15.123", "2026-10-01T20:00:00+00:00").start).toBe("2026-10-01T00:00:00");
  });
});
