import { describe, expect, it, vi } from "vitest";
import { ApiClient, ApiError, takeToken, type Fetch } from "../src/api/client";
import { errorBody, jsonResponse } from "./fixtures";

function recorder(response: Response | Error) {
  const calls: Array<{ url: string; init: RequestInit | undefined }> = [];
  const fetchImpl: Fetch = async (url, init) => {
    calls.push({ url, init });
    if (response instanceof Error) throw response;
    return response;
  };
  return { calls, fetchImpl };
}

describe("ApiClient", () => {
  it("sends the token as X-PAR-Token and asks for the API path", async () => {
    const { calls, fetchImpl } = recorder(jsonResponse(200, { items: [] }));
    await new ApiClient("secret", fetchImpl).devices();
    expect(calls[0]?.url).toBe("/api/v0/devices");
    expect((calls[0]?.init?.headers as Record<string, string>)["X-PAR-Token"]).toBe("secret");
    expect(calls[0]?.init?.credentials).toBe("omit");
  });

  it("sends no token header under the dev proxy (no token)", async () => {
    const { calls, fetchImpl } = recorder(jsonResponse(200, {}));
    await new ApiClient(null, fetchImpl).health();
    expect(calls[0]?.init?.headers).not.toHaveProperty("X-PAR-Token");
  });

  it("asks API-05 with start/end only (offset 0, D-201) and escapes the key", async () => {
    const { calls, fetchImpl } = recorder(jsonResponse(200, {}));
    await new ApiClient("t", fetchImpl).acquisitions("p1", {
      start: "2026-10-18T00:00:00.000",
      end: "2026-10-18T09:30:15.999",
    });
    const url = new URL(calls[0]?.url ?? "", "http://x");
    expect(url.pathname).toBe("/api/v0/devices/p1/acquisitions");
    expect(Object.fromEntries(url.searchParams)).toEqual({
      start: "2026-10-18T00:00:00.000",
      end: "2026-10-18T09:30:15.999",
    });
  });

  it("posts the snapshot import as JSON", async () => {
    const { calls, fetchImpl } = recorder(jsonResponse(201, { snapshot: { key: "p2" } }));
    await new ApiClient("t", fetchImpl).importSnapshot({ source_path: "D:\\a.sqlite3", name: null, position: 2 });
    expect(calls[0]?.init?.method).toBe("POST");
    expect(JSON.parse(String(calls[0]?.init?.body))).toEqual({ source_path: "D:\\a.sqlite3", name: null, position: 2 });
  });

  it("turns the service's error body into an ApiError with code and retryable", async () => {
    const { fetchImpl } = recorder(jsonResponse(503, errorBody("database_unavailable", "库不可访问", true)));
    const error = await new ApiClient("t", fetchImpl).devices().catch((e: unknown) => e);
    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 503, code: "database_unavailable", retryable: true, message: "库不可访问" });
  });

  it("reports a service that cannot be reached as retryable service_unavailable", async () => {
    const { fetchImpl } = recorder(new TypeError("Failed to fetch"));
    const error = await new ApiClient("t", fetchImpl).devices().catch((e: unknown) => e);
    expect(error).toMatchObject({ status: 0, code: "service_unavailable", retryable: true });
  });

  it("never treats an unreadable answer as success", async () => {
    const { fetchImpl } = recorder(new Response("<html>", { status: 200 }));
    const error = await new ApiClient("t", fetchImpl).devices().catch((e: unknown) => e);
    expect(error).toMatchObject({ code: "invalid_response", retryable: true });
    const { fetchImpl: html500 } = recorder(new Response("boom", { status: 500 }));
    expect(await new ApiClient("t", html500).devices().catch((e: unknown) => e)).toMatchObject({
      status: 500,
      code: "internal",
    });
  });
});

describe("takeToken", () => {
  function sources(hash: string, stored: string | null = null) {
    const store = new Map<string, string>(stored ? [["par.token", stored]] : []);
    const replaceState = vi.fn();
    return {
      replaceState,
      store,
      value: {
        location: { hash, pathname: "/", search: "" },
        history: { replaceState },
        storage: { getItem: (k: string) => store.get(k) ?? null, setItem: (k: string, v: string) => void store.set(k, v) },
      },
    };
  }

  it("reads the fragment, strips it from the address bar and keeps it for reloads", () => {
    const s = sources("#token=abc%2Ddef");
    expect(takeToken(s.value)).toBe("abc-def");
    expect(s.replaceState).toHaveBeenCalledWith(null, "", "/");
    expect(s.store.get("par.token")).toBe("abc-def");
  });

  it("falls back to the session copy, then to none (dev proxy)", () => {
    expect(takeToken(sources("", "kept").value)).toBe("kept");
    expect(takeToken(sources("").value)).toBeNull();
  });
});
