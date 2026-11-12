import { spawn } from "node:child_process";
import { rmSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const dbPath = path.join(root, "data", "e2e", "caretwin-e2e.db");
const docPath = path.join(root, "data", "e2e", "documents");
const python =
  process.platform === "win32"
    ? path.join(root, "apps", "api", ".venv", "Scripts", "python.exe")
    : path.join(root, "apps", "api", ".venv", "bin", "python");

for (const suffix of ["", "-wal", "-shm"]) {
  rmSync(`${dbPath}${suffix}`, { force: true });
}
rmSync(docPath, { recursive: true, force: true });

const child = spawn(
  python,
  [
    "-m",
    "uvicorn",
    "app.main:app",
    "--host",
    "127.0.0.1",
    "--port",
    "8000",
  ],
  {
    cwd: path.join(root, "apps", "api"),
    env: {
      ...process.env,
      CARETWIN_ENV: "test",
      CARETWIN_DB_PATH: dbPath,
      CARETWIN_DOCUMENT_STORAGE_PATH: docPath,
      CARETWIN_LOG_LEVEL: "WARNING",
      // Browser tests must always exercise the deterministic path; a developer's
      // real provider key must never be spent (or leak status into) an e2e run.
      GEMINI_API_KEY: "",
    },
    stdio: "inherit",
  },
);

let stopping = false;

function stop() {
  if (stopping) return;
  stopping = true;
  child.kill();
}

process.on("SIGINT", stop);
process.on("SIGTERM", stop);
process.on("exit", stop);
child.on("exit", (code) => process.exit(code ?? 0));
