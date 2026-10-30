/**
 * Development only: `npm run dev` serves the page on 127.0.0.1:5173 and forwards /api to the local service.
 *
 * The browser never sees the token. Each request re-reads <data dir>/service.json (so a restarted service is
 * picked up), adds X-PAR-Token and the service's own Host, and drops Origin/Referer/Cookie. Requests with an
 * Origin other than this dev server, or that the browser marks as coming from another site (Sec-Fetch-Site, which it
 * also sends for an <img> or <script> GET without Origin), are refused, so other web pages cannot use the proxy.
 * The data directory is $PAR_ALPHA_DATA_DIR (tools/ui_v2_dev.py sets it), else the service default.
 */
import { readFileSync } from "node:fs";
import { request as httpRequest, type IncomingMessage, type ServerResponse } from "node:http";
import { homedir } from "node:os";
import { join } from "node:path";
import type { Plugin } from "vite";

export interface ServiceInfo {
  base_url: string;
  token: string;
}

export function defaultDataDir(env: NodeJS.ProcessEnv = process.env): string {
  if (env.PAR_ALPHA_DATA_DIR) return env.PAR_ALPHA_DATA_DIR;
  if (env.LOCALAPPDATA) return join(env.LOCALAPPDATA, "PAR_Spectrometer_2");
  return join(homedir(), ".local", "share", "PAR_Spectrometer_2");
}

export function readServiceInfo(dataDir: string): ServiceInfo | null {
  try {
    const info = JSON.parse(readFileSync(join(dataDir, "service.json"), "utf-8")) as Partial<ServiceInfo>;
    return typeof info.base_url === "string" && typeof info.token === "string"
      ? { base_url: info.base_url, token: info.token }
      : null;
  } catch {
    return null;
  }
}

const DROPPED_HEADERS = new Set(["origin", "referer", "cookie", "host", "connection", "authorization"]);

function fail(res: ServerResponse, status: number, code: string, message: string, detail: string | null): void {
  res.statusCode = status;
  res.setHeader("Content-Type", "application/json; charset=utf-8");
  res.end(JSON.stringify({ error: { code, message, retryable: status >= 500, detail } }));
}

export interface Refusal {
  message: string;
  detail: string | null;
}

const SAME_ORIGIN_FETCH = new Set(["same-origin", "none"]);

/** Why a request to the proxy is refused (403 forbidden_origin), or null when it comes from the dev page. */
export function refusal(headers: Record<string, string | string[] | undefined>, port: number | undefined): Refusal | null {
  const hosts = [`127.0.0.1:${port}`, `localhost:${port}`];
  const host = typeof headers.host === "string" ? headers.host : "";
  const origin = headers.origin;
  const site = headers["sec-fetch-site"];
  if (!hosts.includes(host)) return { message: "请求的 Host 不是开发服务器地址", detail: host || null };
  if (origin !== undefined && !hosts.map((name) => `http://${name}`).includes(String(origin))) {
    return { message: "跨站请求被拒绝（开发代理）", detail: String(origin) };
  }
  if (site !== undefined && !SAME_ORIGIN_FETCH.has(String(site))) {
    return { message: "跨站请求被拒绝（开发代理）", detail: String(site) };
  }
  return null;
}

export function forward(req: IncomingMessage, res: ServerResponse, info: ServiceInfo): void {
  const target = new URL(req.url ?? "/", info.base_url);
  const headers: Record<string, string | string[]> = {};
  for (const [name, value] of Object.entries(req.headers)) {
    if (value !== undefined && !DROPPED_HEADERS.has(name)) headers[name] = value;
  }
  headers["host"] = target.host;
  headers["x-par-token"] = info.token;
  const upstream = httpRequest(target, { method: req.method, headers }, (answer) => {
    res.writeHead(answer.statusCode ?? 502, answer.headers);
    answer.pipe(res);
  });
  upstream.on("error", (error) =>
    fail(res, 502, "service_unavailable", "本机服务未响应（开发代理）", String(error)),
  );
  req.pipe(upstream);
}

export function parServiceProxy(dataDir: string = defaultDataDir()): Plugin {
  return {
    name: "par-service-proxy",
    apply: "serve",
    configureServer(server) {
      // Registered before Vite's own host check, so this middleware checks Host itself (DNS rebinding).
      server.middlewares.use("/api", (req, res) => {
        const refused = refusal(req.headers, server.config.server.port);
        if (refused !== null) {
          fail(res, 403, "forbidden_origin", refused.message, refused.detail);
          return;
        }
        const info = readServiceInfo(dataDir);
        if (info === null) {
          fail(res, 503, "service_unavailable", `本机服务未启动：${join(dataDir, "service.json")} 不存在`, null);
          return;
        }
        req.url = `/api${req.url ?? ""}`; // connect strips the mount path
        forward(req, res, info);
      });
    },
  };
}
