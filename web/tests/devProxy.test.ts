import { describe, expect, it } from "vitest";
import { refusal } from "../dev-proxy";

describe("dev proxy access check", () => {
  const port = 5173;

  it("lets the dev page through", () => {
    expect(refusal({ host: "127.0.0.1:5173", origin: "http://127.0.0.1:5173" }, port)).toBeNull();
    expect(refusal({ host: "localhost:5173", "sec-fetch-site": "same-origin" }, port)).toBeNull();
  });

  it("refuses another Host or Origin", () => {
    expect(refusal({ host: "evil.example:5173" }, port)?.detail).toBe("evil.example:5173");
    expect(refusal({ host: "127.0.0.1:5173", origin: "http://evil.example" }, port)?.detail).toBe("http://evil.example");
  });

  it("refuses a cross-site request that carries no Origin (an <img> or <script> GET, review N-6)", () => {
    expect(refusal({ host: "127.0.0.1:5173", "sec-fetch-site": "cross-site" }, port)?.detail).toBe("cross-site");
    expect(refusal({ host: "127.0.0.1:5173", "sec-fetch-site": "same-site" }, port)?.detail).toBe("same-site");
  });
});
