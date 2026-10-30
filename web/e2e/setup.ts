/**
 * Playwright global setup: start the real service (python -m par_app.service_main) on 127.0.0.1 with the built page and a
 * fresh data directory holding three synthetic device databases registered in its tier-1 configuration (issue #82:
 * the pages show only the alpha's own device databases). The tier is raised to 1 through the API after the start, so
 * the service never starts acquiring by itself (#92) and no port is opened: p1 温室外,
 * p2 温室内 (the same light through a made-up greenhouse cover 20 s later, the calculation page's B) and p3 光积累
 * (one record a minute, for DLI). The connection
 * reaches the tests through PAR_E2E_* variables; the returned teardown stops the service and removes the scratch
 * directory. Python comes from $PAR_E2E_PYTHON, the repository's .venv, or `python` on PATH (CI).
 */
import { spawn, spawnSync, type ChildProcess } from "node:child_process";
import { existsSync, mkdtempSync, readFileSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const root = resolve(dirname(fileURLToPath(import.meta.url)), "..", "..");
const dist = join(root, "web", "dist");
const START_TIMEOUT_MS = 30_000;
const STOP_TIMEOUT_MS = 10_000;

function python(): string {
  if (process.env.PAR_E2E_PYTHON) return process.env.PAR_E2E_PYTHON;
  const venv = join(root, ".venv", ...(process.platform === "win32" ? ["Scripts", "python.exe"] : ["bin", "python"]));
  return existsSync(venv) ? venv : "python";
}

interface ServiceInfo {
  base_url: string;
  token: string;
  port: number;
}

async function waitReady(child: ChildProcess, serviceFile: string, stderr: () => string): Promise<ServiceInfo> {
  const deadline = Date.now() + START_TIMEOUT_MS;
  while (Date.now() < deadline) {
    if (child.exitCode !== null) throw new Error(`service exited with ${child.exitCode}: ${stderr()}`);
    try {
      const info = JSON.parse(readFileSync(serviceFile, "utf-8")) as ServiceInfo;
      const health = await fetch(`${info.base_url}/api/v0/health`);
      if (health.ok) return info;
    } catch {
      // not listening yet
    }
    await new Promise((wake) => setTimeout(wake, 100));
  }
  throw new Error(`service not ready within ${START_TIMEOUT_MS / 1000} s: ${stderr()}`);
}

/** Tier 0 -> 1 with the two-step confirmation, as the settings page does it (16_ 4.3). */
async function tierOne(info: ServiceInfo): Promise<void> {
  const headers = { "X-PAR-Token": info.token, "Content-Type": "application/json" };
  const issued = await fetch(`${info.base_url}/api/v0/tier/confirmations`, {
    method: "POST",
    headers,
    body: JSON.stringify({ tier: 1 }),
  });
  if (issued.status !== 201) throw new Error(`tier confirmation answered ${issued.status}: ${await issued.text()}`);
  const { confirmation_id: confirmation } = (await issued.json()) as { confirmation_id: string };
  const raised = await fetch(`${info.base_url}/api/v0/tier`, {
    method: "PUT",
    headers,
    body: JSON.stringify({ tier: 1, confirmation_id: confirmation }),
  });
  if (raised.status !== 200) throw new Error(`PUT /tier answered ${raised.status}: ${await raised.text()}`);
}

export default async function globalSetup(): Promise<() => Promise<void>> {
  if (!existsSync(join(dist, "index.html"))) {
    throw new Error("web/dist is not built: run `npm run build` first (the e2e tests exercise the built page)");
  }
  const scratch = mkdtempSync(join(tmpdir(), "par-e2e-"));
  const dataDir = join(scratch, "alpha");
  const devicesDir = join(dataDir, "data", "devices");
  const sourceDb = join(devicesDir, "温室外.sqlite3");
  const wrote = spawnSync(
    python(),
    [join(root, "tools", "ui_v2_demo_db.py"), sourceDb, "--day", "2026-10-01", "--every-minutes", "30"],
    { cwd: root, encoding: "utf-8" },
  );
  if (wrote.status !== 0) throw new Error(`ui_v2_demo_db.py failed: ${wrote.stderr || wrote.error}`);
  const secondDb = join(devicesDir, "温室内.sqlite3");
  const second = spawnSync(
    python(),
    [
      join(root, "tools", "ui_v2_demo_db.py"),
      secondDb,
      ...["--day", "2026-10-01", "--every-minutes", "30", "--offset-seconds", "20", "--filter", "greenhouse"],
    ],
    { cwd: root, encoding: "utf-8" },
  );
  if (second.status !== 0) throw new Error(`ui_v2_demo_db.py failed: ${second.stderr || second.error}`);
  // the DLI page needs records one minute apart: 30-minute records never form an integrated segment (allowed gap 120 s)
  const dliDb = join(devicesDir, "光积累.sqlite3");
  const wroteDli = spawnSync(
    python(),
    [join(root, "tools", "ui_v2_demo_db.py"), dliDb, "--day", "2026-10-01", "--every-minutes", "1"],
    { cwd: root, encoding: "utf-8" },
  );
  if (wroteDli.status !== 0) throw new Error(`ui_v2_demo_db.py failed: ${wroteDli.stderr || wroteDli.error}`);
  const registered = spawnSync(
    python(),
    [
      join(root, "tools", "ui_v2_e2e_devices.py"),
      dataDir,
      ...["温室外", sourceDb, "温室内", secondDb, "光积累", dliDb],
    ],
    { cwd: root, encoding: "utf-8" },
  );
  if (registered.status !== 0) throw new Error(`ui_v2_e2e_devices.py failed: ${registered.stderr || registered.error}`);

  const child = spawn(
    python(),
    // tier 0 first (issue #119 made 1 the product's default): setup raises it through the API, so no port opens
    ["-m", "par_app.service_main", "--port", "0", "--data-dir", dataDir, "--web-dir", dist, "--first-run-tier", "0"],
    { cwd: root, stdio: ["ignore", "ignore", "pipe"] },
  );
  let stderr = "";
  child.stderr?.on("data", (chunk: Buffer) => (stderr += chunk.toString()));
  let info: ServiceInfo;
  try {
    info = await waitReady(child, join(dataDir, "service.json"), () => stderr);
  } catch (error) {
    child.kill("SIGKILL");
    rmSync(scratch, { recursive: true, force: true });
    throw error;
  }
  try {
    await tierOne(info);
  } catch (error) {
    child.kill("SIGKILL");
    rmSync(scratch, { recursive: true, force: true });
    throw error;
  }
  process.env.PAR_E2E_BASE_URL = info.base_url;
  process.env.PAR_E2E_TOKEN = info.token;
  process.env.PAR_E2E_PORT = String(info.port);
  process.env.PAR_E2E_SOURCE_DB = sourceDb;
  process.env.PAR_E2E_SOURCE_DB2 = secondDb;
  process.env.PAR_E2E_DATA_DIR = dataDir;
  process.env.PAR_E2E_DLI_DB = dliDb;

  return async () => {
    child.kill("SIGTERM");
    const gone = new Promise<void>((done) => child.once("exit", () => done()));
    const timer = setTimeout(() => child.kill("SIGKILL"), STOP_TIMEOUT_MS);
    await gone;
    clearTimeout(timer);
    rmSync(scratch, { recursive: true, force: true });
  };
}
