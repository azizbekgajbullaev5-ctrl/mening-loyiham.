"use client";
import type { ModuleEstimate } from "@/lib/types";

function duration(sec: number): string {
  if (sec < 60) return `${Math.max(1, Math.round(sec))} s`;
  return `${Math.round(sec / 60)} daq`;
}

/** Checkbox list of plagiarism modules. With ``showEstimate`` it shows requests / downloads / price / time per module. */
export function ModulePicker({ modules, selected, onChange, showEstimate = false }: {
  modules: ModuleEstimate[];
  selected: string[];
  onChange: (keys: string[]) => void;
  showEstimate?: boolean;
}) {
  const toggle = (key: string, on: boolean) => {
    const order = modules.map((m) => m.key);
    const next = on ? [...selected, key] : selected.filter((k) => k !== key);
    onChange(order.filter((k) => next.includes(k)));
  };
  const groups: [string, ModuleEstimate[]][] = [
    ["Lokal modullar (internet va pul kerak emas)", modules.filter((m) => m.kind === "local")],
    ["Onlayn modullar", modules.filter((m) => m.kind === "online")],
  ];
  return (
    <div className="space-y-4" data-testid="module-picker">
      {groups.map(([title, list]) => (
        <div key={title}>
          <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-500">{title}</p>
          <ul className="grid gap-2 sm:grid-cols-2">
            {list.map((m) => {
              const on = selected.includes(m.key) && m.available;
              return (
                <li key={m.key} className={`rounded-lg border p-3 ${on ? "border-brand-300 bg-brand-50/40" : "border-slate-200"} ${m.available ? "" : "opacity-60"}`}>
                  <label className="flex items-start gap-2 text-sm">
                    <input type="checkbox" className="mt-1" checked={on} disabled={!m.available} onChange={(e) => toggle(m.key, e.target.checked)}
                      data-testid={`module-${m.key}`} />
                    <span className="min-w-0">
                      <span className="font-medium text-slate-800">{m.label}</span>
                      {m.paid && <span className="ml-1 rounded bg-amber-100 px-1 text-[10px] font-semibold text-amber-800">pullik</span>}
                      <span className="block text-xs text-slate-500">{m.description}</span>
                      {!m.available && <span className="block text-xs text-amber-700">{m.reason}</span>}
                      {showEstimate && m.available && m.kind === "online" && (
                        <span className="mt-1 block text-xs text-slate-700">
                          {m.queries} so&apos;rov{m.requests !== m.queries ? ` (${m.requests} API chaqiruvi)` : ""}
                          {m.downloads ? ` · ≤ ${m.downloads} yuklab olish` : ""} · ≈ {duration(m.seconds)} ·{" "}
                          <b>{m.cost_usd > 0 ? `≈ $${m.cost_usd.toFixed(3)}` : "bepul"}</b>
                          {m.sources?.length ? <span className="block text-slate-500">{m.sources.join(", ")}</span> : null}
                        </span>
                      )}
                    </span>
                  </label>
                </li>
              );
            })}
          </ul>
        </div>
      ))}
    </div>
  );
}

export function estimateTotals(modules: ModuleEstimate[], selected: string[]) {
  const on = modules.filter((m) => selected.includes(m.key) && m.available);
  return {
    cost: on.reduce((a, m) => a + m.cost_usd, 0),
    requests: on.reduce((a, m) => a + m.requests, 0),
    seconds: on.reduce((a, m) => a + m.seconds, 0),
    online: on.filter((m) => m.kind === "online").length,
  };
}
