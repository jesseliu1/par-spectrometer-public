import { mkdirSync, mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
// @ts-expect-error plain ES module without types
import { violations } from "../scripts/check-tokens.mjs";

describe("check-tokens (R-1-5)", () => {
  it("passes the real sources", () => {
    expect(violations(join(__dirname, "..", "src"))).toEqual([]);
  });

  it("flags hex and rgb()/hsl() outside tokens.css and allows them inside", () => {
    const root = mkdtempSync(join(tmpdir(), "tokens-"));
    mkdirSync(join(root, "styles"));
    writeFileSync(join(root, "styles", "tokens.css"), ":root { --a: #fff; --b: rgba(0, 0, 0, 0.5); }");
    writeFileSync(join(root, "a.vue"), "<template><b #default>x</b></template>\n<style>.x { color: #1d4ed8; }</style>");
    writeFileSync(join(root, "b.ts"), "const c = 'hsl(10, 20%, 30%)';");
    expect((violations(root) as string[]).map((line) => line.split(":")[0])).toEqual(["a.vue", "b.ts"]);
  });

  it("flags CSS colour functions and named colours too, but not transparent/currentColor (review N-1)", () => {
    const root = mkdtempSync(join(tmpdir(), "tokens-"));
    const cases: Record<string, string> = {
      "hwb.css": ".x { color: hwb(10 20% 30%); }",
      "lab.css": ".x { color: lab(50% 40 59.5); }",
      "lch.css": ".x { background: lch(52% 72 56); }",
      "oklch.css": ".x { color: oklch(70% 0.1 200); }",
      "oklab.css": ".x { color: oklab(0.6 0.1 0.1); }",
      "fn.css": ".x { color: color(display-p3 1 0 0); }",
      "mix.css": ".x { color: color-mix(in srgb, var(--a), var(--b)); }",
      "named.css": ".x { border: 1px solid red; }",
      "named.vue": "<style>.x { background-color: WhiteSmoke; }</style>",
      "named.ts": 'const option = { itemStyle: { color: "red" }, borderColor: \'navy\' };',
      "ok.css": ".x { color: transparent; border-color: currentColor; background: var(--color-surface); }",
      "ok.ts": 'const label = "red"; // a word, not a colour property\nconst text = token("--color-red");',
    };
    for (const [name, text] of Object.entries(cases)) writeFileSync(join(root, name), text);
    const flagged = (violations(root) as string[]).map((line) => line.split(":")[0]).sort();
    expect(flagged).toEqual(Object.keys(cases).filter((name) => !name.startsWith("ok.")).sort());
  });
});

