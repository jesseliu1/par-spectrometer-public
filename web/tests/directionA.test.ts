/**
 * Direction A (实验室仪表, S-9:负责人 picked A on 2026-10-18) token contract. The values come from
 * docs/design/ui-v2-pages.md 3.4 (direction A column, sourced from the V1.0.x par_app/theme.py) with the
 * notes of docs/design/ui-v2/方向对比.md applied: the accent stays the V1.0.x #2563eb (not Stitch's
 * #0284c7), KPI cards are compressed (22px telemetry size from stitch/A-design.md, not the 28px of the
 * pre-Stitch draft), and numerals use a monospace stack with tabular figures. JetBrains Mono ships with the
 * app (web/fonts, loaded by @font-face from /fonts/, never online) so every PC renders the screenshots' glyphs;
 * CJK falls to the bundled Noto Sans SC before any system font.
 * Every text/background pair used on surfaces must stay WCAG AA (≥ 4.5:1), as the header of tokens.css
 * promises (disabled is exempt, WCAG 1.4.3 inactive controls).
 */
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const tokensCss = readFileSync(join(__dirname, "..", "src", "styles", "tokens.css"), "utf-8");
const baseCss = readFileSync(join(__dirname, "..", "src", "styles", "base.css"), "utf-8");

function token(name: string): string {
  const match = tokensCss.match(new RegExp(`${name}:\\s*([^;]+);`));
  if (!match?.[1]) throw new Error(`token ${name} not found in tokens.css`);
  return match[1].trim();
}

function luminance(hex: string): number {
  const channel = (raw: number): number => {
    const c = raw / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  const value = hex.replace("#", "");
  const [r = 0, g = 0, b = 0] = [0, 2, 4].map((i) => channel(Number.parseInt(value.slice(i, i + 2), 16)));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
}

function contrast(a: string, b: string): number {
  const [hi = 0, lo = 0] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

describe("direction A tokens (S-9, docs/design/ui-v2-pages.md 3.4)", () => {
  it("uses the V1.0.x lab-instrument palette with the #2563eb accent", () => {
    expect(token("--color-background")).toBe("#f5f7fb");
    expect(token("--color-on-background")).toBe("#172033");
    expect(token("--color-surface")).toBe("#ffffff");
    expect(token("--color-on-surface")).toBe("#172033");
    expect(token("--color-primary")).toBe("#2563eb");
    expect(token("--color-outline-variant")).toBe("#dbe3ef");
    expect(token("--color-disabled")).toBe("#94a3b8");
    expect(token("--chart-spectrum")).toBe("#2563eb");
    expect(token("--chart-grid")).toBe("#e2e8f0");
  });

  it("gives numerals the bundled JetBrains Mono, then the bundled Noto Sans SC, and tabular figures", () => {
    const mono = token("--font-family-mono")
      .split(",")
      .map((family) => family.trim());
    expect(mono.slice(0, 2)).toEqual(['"JetBrains Mono"', '"Noto Sans SC"']);
    expect(mono.at(-1)).toBe("monospace");
    expect(token("--font-numeric")).toBe("tabular-nums");
    // base.css .numeric applies the stack (components only tag elements with the class)
    expect(baseCss).toMatch(/\.numeric\s*{[^}]*font-family:\s*var\(--font-family-mono\)/);
  });

  it("loads JetBrains Mono from the bundle, never from the network (UI-001, PR #48 review question 1)", () => {
    const face = baseCss.match(/@font-face\s*{[^}]*font-family:\s*"JetBrains Mono"[^}]*}/)?.[0] ?? "";
    expect(face).toContain('url("/fonts/JetBrainsMono.ttf")');
    expect(face).toMatch(/font-weight:\s*100 800/);
    expect(baseCss).not.toMatch(/url\(\s*["']?(https?:)?\/\//);
    const fonts = join(__dirname, "..", "fonts");
    expect(readFileSync(join(fonts, "JetBrainsMono.ttf")).subarray(0, 4)).toEqual(Buffer.from([0, 1, 0, 0]));
    expect(readFileSync(join(fonts, "JetBrainsMono-OFL.txt"), "utf-8")).toContain("SIL Open Font License, Version 1.1");
  });

  it("compresses the KPI cards and keeps the V1.0.x chrome sizes", () => {
    expect(token("--font-size-kpi")).toBe("22px");
    expect(token("--nav-height")).toBe("42px");
    expect(token("--elevation-1")).toBe("none");
  });

  it("keeps every text/background pair WCAG AA (≥ 4.5:1)", () => {
    const surface = token("--color-surface");
    const background = token("--color-background");
    const pairs: Array<[string, string]> = [
      [token("--color-on-background"), background],
      [token("--color-on-surface"), surface],
      [token("--color-on-surface-variant"), surface],
      [token("--color-primary"), surface],
      [token("--color-primary"), background],
      [token("--color-error"), surface],
      [token("--color-error"), background],
      [token("--color-warning"), surface],
      [token("--color-success"), surface],
      [token("--color-on-primary"), token("--color-primary")],
      [token("--color-on-primary-container"), token("--color-primary-container")],
      [token("--color-on-error-container"), token("--color-error-container")],
      [token("--color-on-warning-container"), token("--color-warning-container")],
    ];
    for (const [text, backdrop] of pairs) {
      expect(contrast(text, backdrop), `${text} on ${backdrop}`).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("keeps the record table's status text AA on every row background it renders, selected included (review M-1)", () => {
    // read the combinations from the component itself, so a changed row background or status colour is re-checked
    const table = readFileSync(join(__dirname, "..", "src", "components", "RecordTable.vue"), "utf-8");
    const colourOf = (selector: string, property: "background" | "color"): string => {
      const escaped = selector.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      const blocks = [...table.matchAll(new RegExp(`(?:^|\\n)${escaped}\\s*{([^}]*)}`, "g"))].map((match) => match[1] ?? "");
      const declaration = new RegExp(`(?:^|[\\s;])${property}:\\s*var\\((--[\\w-]+)\\)`);
      const name = blocks.map((block) => block.match(declaration)?.[1]).find((found) => found !== undefined);
      if (!name) throw new Error(`${selector} has no ${property} token in RecordTable.vue`);
      return token(name);
    };
    const rows: Record<string, string> = {
      plain: token("--color-surface"), // the table sits on a .panel
      hover: colourOf("tbody tr:hover", "background"),
      selected: colourOf("tbody tr.selected", "background"),
    };
    const hasRule = (selector: string): boolean => new RegExp(`(?:^|\\n)${selector.replace(/\./g, "\\.")}\\s*{`).test(table);
    for (const status of [".ok", ".failed", ".warn"]) {
      for (const [row, backdrop] of Object.entries(rows)) {
        // a selected row may give the status its own, darker shade of the same colour; otherwise the plain one shows
        const own = `tr.selected ${status}`;
        const text = row === "selected" && hasRule(own) ? colourOf(own, "color") : colourOf(status, "color");
        expect(contrast(text, backdrop), `${status} on the ${row} row`).toBeGreaterThanOrEqual(4.5);
      }
    }
  });
});
