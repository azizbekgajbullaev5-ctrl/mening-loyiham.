// Build the static UI and copy it to backend/webui (served by FastAPI).
//   npm run build:webui
import { spawnSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const out = path.join(root, "out");
const target = path.resolve(root, "..", "backend", "webui");

fs.rmSync(path.join(root, ".next"), { recursive: true, force: true });
fs.rmSync(out, { recursive: true, force: true });
const r = spawnSync(process.platform === "win32" ? "npx.cmd" : "npx", ["next", "build"], {
  cwd: root,
  stdio: "inherit",
  env: { ...process.env, STATIC_EXPORT: "1", NEXT_TELEMETRY_DISABLED: "1" },
  shell: process.platform === "win32",
});
if (r.status !== 0) process.exit(r.status ?? 1);
fs.rmSync(target, { recursive: true, force: true });
fs.cpSync(out, target, { recursive: true });
fs.rmSync(path.join(root, ".next"), { recursive: true, force: true }); // don't leave export build for `next start`
console.log(`web UI copied to ${target}`);
