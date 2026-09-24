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

// Drop the legacy-browser polyfills bundle (loaded only via <script noModule>, i.e. never by browsers that
// support ES modules — every browser this UI supports). It contains old-IE code such as
// `new ActiveXObject("htmlfile")`, which antivirus heuristics associate with script droppers.
const chunks = path.join(out, "_next", "static", "chunks");
for (const f of fs.readdirSync(chunks)) if (/^polyfills-.*\.js$/.test(f)) fs.rmSync(path.join(chunks, f));
const walk = (dir) => fs.readdirSync(dir, { withFileTypes: true }).flatMap((e) => (e.isDirectory() ? walk(path.join(dir, e.name)) : [path.join(dir, e.name)]));
for (const file of walk(out).filter((f) => f.endsWith(".html"))) {
  const html = fs.readFileSync(file, "utf8");
  const cleaned = html.replace(/<script[^>]*polyfills-[^"]*\.js"[^>]*><\/script>/g, "");
  if (cleaned !== html) fs.writeFileSync(file, cleaned);
}
const leftovers = walk(out).filter((f) => /\.(js|html)$/.test(f) && fs.readFileSync(f, "utf8").includes("ActiveXObject"));
if (leftovers.length) {
  console.error("ActiveXObject still present in:", leftovers);
  process.exit(1);
}

fs.rmSync(target, { recursive: true, force: true });
fs.cpSync(out, target, { recursive: true });
fs.rmSync(path.join(root, ".next"), { recursive: true, force: true }); // don't leave export build for `next start`
console.log(`web UI copied to ${target}`);
