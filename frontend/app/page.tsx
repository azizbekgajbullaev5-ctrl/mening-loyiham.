"use client";
import { useCallback, useEffect, useState } from "react";
import { AnalysesTable } from "@/components/AnalysesTable";
import { AppShell } from "@/components/AppShell";
import { UploadCard } from "@/components/UploadCard";
import { get } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { AnalysisSummary } from "@/lib/types";

function Dashboard() {
  const [items, setItems] = useState<AnalysisSummary[]>([]);
  const load = useCallback(() => get<AnalysisSummary[]>("/analyses?limit=100").then(setItems).catch(() => {}), []);
  useEffect(() => {
    load();
  }, [load]);
  // poll while something is still running
  useEffect(() => {
    if (!items.some((a) => a.status === "queued" || a.status === "running")) return;
    const id = setInterval(load, 2000);
    return () => clearInterval(id);
  }, [items, load]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{t.appName}</h1>
        <p className="text-sm text-slate-500">{t.appTagline}</p>
      </div>
      <div className="grid gap-6 lg:grid-cols-3">
        <div className="lg:col-span-1"><UploadCard onUploaded={load} /></div>
        <div className="lg:col-span-2"><AnalysesTable items={items} onChanged={load} /></div>
      </div>
    </div>
  );
}

export default function Page() {
  return (
    <AppShell>
      <Dashboard />
    </AppShell>
  );
}
