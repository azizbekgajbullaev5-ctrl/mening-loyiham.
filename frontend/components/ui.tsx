import type { ReactNode } from "react";
import type { Confidence } from "@/lib/types";
import { t } from "@/lib/i18n";

export function Card({ title, subtitle, actions, children, className = "" }: { title?: ReactNode; subtitle?: ReactNode; actions?: ReactNode; children: ReactNode; className?: string }) {
  return (
    <section className={`card ${className}`}>
      {(title || actions) && (
        <header className="flex flex-wrap items-start justify-between gap-2 border-b border-slate-100 px-5 py-3">
          <div>
            {title && <h2 className="text-base font-semibold text-slate-900">{title}</h2>}
            {subtitle && <p className="text-xs text-slate-500">{subtitle}</p>}
          </div>
          {actions}
        </header>
      )}
      <div className="p-5">{children}</div>
    </section>
  );
}

const confCls: Record<Confidence, string> = {
  low: "bg-slate-100 text-slate-700 ring-slate-200",
  medium: "bg-amber-50 text-amber-800 ring-amber-200",
  high: "bg-brand-50 text-brand-700 ring-brand-200",
};

export function ConfidenceBadge({ value }: { value: Confidence | null | undefined }) {
  if (!value) return <span className="text-slate-400">—</span>;
  return (
    <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ring-1 ${confCls[value]}`}>
      {t.confidence[value]}
    </span>
  );
}

const statusCls: Record<string, string> = {
  queued: "bg-slate-100 text-slate-700",
  running: "bg-brand-50 text-brand-700",
  completed: "bg-emerald-50 text-emerald-800",
  failed: "bg-red-50 text-red-700",
};

export function StatusBadge({ status, progress, queue }: { status: string; progress?: number; queue?: number | null }) {
  return (
    <span className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 text-xs font-medium ${statusCls[status] ?? ""}`}>
      {status === "running" && <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-brand-500" aria-hidden />}
      {t.status[status] ?? status}
      {status === "running" && progress !== undefined ? ` ${progress}%` : ""}
      {status === "queued" && queue ? ` (${queue})` : ""}
    </span>
  );
}

export function Spinner({ label = t.common.loading }: { label?: string }) {
  return (
    <div className="flex items-center gap-2 text-sm text-slate-500" role="status">
      <span className="h-4 w-4 animate-spin rounded-full border-2 border-slate-300 border-t-brand-600" aria-hidden />
      {label}
    </div>
  );
}

export function ProgressBar({ value }: { value: number }) {
  return (
    <div className="h-2.5 w-full overflow-hidden rounded-full bg-brand-100" role="progressbar" aria-valuenow={value} aria-valuemin={0} aria-valuemax={100}>
      <div className="h-full rounded-full bg-brand-600 transition-all" style={{ width: `${Math.max(2, value)}%` }} />
    </div>
  );
}

export function Notice({ children, tone = "info" }: { children: ReactNode; tone?: "info" | "warn" }) {
  const cls = tone === "info" ? "border-brand-200 bg-brand-50 text-brand-900" : "border-amber-200 bg-amber-50 text-amber-900";
  return <div className={`rounded-lg border px-4 py-3 text-sm ${cls}`}>{children}</div>;
}
