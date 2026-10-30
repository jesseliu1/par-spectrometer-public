import { describe, expect, it } from "vitest";
import { ApiError } from "../src/api/client";
import { createResource, invalidate, reset, run } from "../src/lib/resource";

const unavailable = () => new ApiError(503, { code: "database_unavailable", message: "库不可访问", retryable: true, detail: null });
const gone = () => new ApiError(404, { code: "record_not_found", message: "记录不存在", retryable: false, detail: null });

describe("resource keeps the last valid data (R-1-5)", () => {
  it("replaces data on success and clears the error", async () => {
    const resource = createResource<number>();
    expect(await run(resource, async () => 1)).toBe(true);
    expect(resource).toMatchObject({ data: 1, error: null, loading: false });
  });

  it("keeps the old data when a later load fails, and says why", async () => {
    const resource = createResource<number>();
    await run(resource, async () => 1);
    expect(await run(resource, async () => Promise.reject(unavailable()))).toBe(false);
    expect(resource.data).toBe(1);
    expect(resource.error?.code).toBe("database_unavailable");
    expect(resource.loading).toBe(false);
  });

  it("retry repeats the failed call and recovers", async () => {
    const resource = createResource<number>();
    let attempts = 0;
    await run(resource, async () => {
      attempts += 1;
      if (attempts === 1) throw unavailable();
      return 2;
    });
    expect(resource.error).not.toBeNull();
    expect(await resource.retry?.()).toBe(true);
    expect(resource).toMatchObject({ data: 2, error: null });
  });

  it("clears the data only for the named codes (UI-032: a record that is gone)", async () => {
    const resource = createResource<number>();
    await run(resource, async () => 1);
    await run(resource, async () => Promise.reject(gone()), ["record_not_found"]);
    expect(resource.data).toBeNull();
    expect(resource.error?.code).toBe("record_not_found");
  });

  it("wraps a non-API failure instead of hiding it", async () => {
    const resource = createResource<number>();
    await run(resource, async () => Promise.reject(new Error("boom")));
    expect(resource.error).toMatchObject({ code: "internal", retryable: true });
  });

  it("drops a slow answer to a superseded call", async () => {
    const resource = createResource<string>();
    let release: (value: string) => void = () => undefined;
    const slow = run(resource, () => new Promise<string>((resolve) => (release = resolve)));
    await run(resource, async () => "new");
    release("old");
    expect(await slow).toBe(false);
    expect(resource.data).toBe("new");
  });

  it("invalidate keeps the data but drops pending answers (review M-1)", async () => {
    const resource = createResource<string>();
    await run(resource, async () => "shown");
    let release: (value: string) => void = () => undefined;
    const pending = run(resource, () => new Promise<string>((resolve) => (release = resolve)));
    invalidate(resource);
    expect(resource.loading).toBe(false);
    release("late");
    expect(await pending).toBe(false);
    expect(resource).toMatchObject({ data: "shown", error: null, loading: false });
  });

  it("invalidate drops the retry of the load it cancelled (review question)", async () => {
    const resource = createResource<string>();
    await run(resource, async () => "shown");
    void run(resource, () => new Promise<string>(() => undefined)); // never answers
    expect(resource.retry).not.toBeNull();
    invalidate(resource);
    expect(resource).toMatchObject({ data: "shown", error: null, loading: false, retry: null });
  });

  it("reset forgets data and error and drops pending answers", async () => {
    const resource = createResource<string>();
    let release: (value: string) => void = () => undefined;
    const pending = run(resource, () => new Promise<string>((resolve) => (release = resolve)));
    reset(resource);
    release("late");
    await pending;
    expect(resource).toMatchObject({ data: null, error: null, loading: false });
  });
});
