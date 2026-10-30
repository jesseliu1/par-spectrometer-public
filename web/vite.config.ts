import { copyFileSync, createReadStream, mkdirSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import vue from "@vitejs/plugin-vue";
import type { Plugin } from "vite";
import { defineConfig } from "vitest/config";
import { parServiceProxy } from "./dev-proxy.ts";

const here = dirname(fileURLToPath(import.meta.url));
const SHARED_FONT_DIR = resolve(here, "..", "resources", "fonts"); // shared with the V1.0.x PyQt5 UI
const WEB_FONT_DIR = resolve(here, "fonts"); // web only, so the V1.0.x package does not grow
/** Published at /fonts/<name>: each font with its SIL OFL 1.1 licence. */
const FONT_FILES: ReadonlyArray<readonly [name: string, dir: string]> = [
  ["NotoSansSC.ttf", SHARED_FONT_DIR],
  ["OFL.txt", SHARED_FONT_DIR],
  ["JetBrainsMono.ttf", WEB_FONT_DIR],
  ["JetBrainsMono-OFL.txt", WEB_FONT_DIR],
];

/**
 * UI-001: the bundled fonts are served at /fonts/, never an online font: Noto Sans SC (resources/fonts) for text,
 * JetBrains Mono 2.304 (web/fonts, D-205 / PR #48 review question 1) for numerals.
 */
function bundledFont(): Plugin {
  return {
    name: "par-bundled-font",
    configureServer(server) {
      for (const [name, dir] of FONT_FILES) {
        if (!name.endsWith(".ttf")) continue;
        server.middlewares.use(`/fonts/${name}`, (_req, res) => {
          res.setHeader("Content-Type", "font/ttf");
          createReadStream(join(dir, name)).pipe(res);
        });
      }
    },
    writeBundle(options) {
      const target = join(options.dir ?? resolve(here, "dist"), "fonts");
      mkdirSync(target, { recursive: true });
      for (const [name, dir] of FONT_FILES) copyFileSync(join(dir, name), join(target, name));
    },
  };
}

export default defineConfig({
  plugins: [vue(), bundledFont(), parServiceProxy()],
  publicDir: false,
  // the company logo is the repository's logo.png (also the window icon), imported by src/lib/brand.ts
  server: { host: "127.0.0.1", port: 5173, strictPort: true, fs: { allow: [here, resolve(here, "..", "logo.png")] } },
  preview: { host: "127.0.0.1" },
  build: { outDir: "dist", emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 1500 },
  test: { environment: "happy-dom", include: ["tests/**/*.test.ts"] },
});
