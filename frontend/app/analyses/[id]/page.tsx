"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ChaptersCharts } from "@/components/Charts";
import { AcademicPanel, ChaptersTable, DocumentViewer, MethodPanel, OverviewPanel, PassagesPanel, SimilarityPanel } from "@/components/ResultPanels";
import { Card, Notice, ProgressBar, Spinner, StatusBadge } from "@/components/ui";
import { get, post } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { AnalysisDetail, AnalysisSummary, SectionRow } from "@/lib/types";

type Tab = keyof typeof t.result.tabs;

function Progress({ a }: { a: AnalysisDetail }) {
  return (
    <Card title={a.document_name ?? ""} subtitle={`${t.depths[a.depth]} · ${t.status[a.status]}`}>
      <div className="space-y-3">
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium text-slate-700">{t.stages[a.stage] ?? a.stage}{a.message ? `: ${a.message}` : ""}</span>
          <span className="tabular-nums text-slate-500">{a.progress}%</span>
        </div>
        <ProgressBar value={a.progress} />
        <ol className="grid gap-1 text-xs text-slate-500 sm:grid-cols-3">
          {["extracting", "language", "segmenting", "ai_analysis", "similarity", "style", "academic", "aggregating"].map((s) => (
            <li key={s} className={a.stage === s ? "font-semibold text-brand-700" : ""}>• {t.stages[s]}</li>
          ))}
        </ol>
      </div>
    </Card>
  );
}

function ResultView() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const [a, setA] = useState<AnalysisDetail | null>(null);
  const [sections, setSections] = useState<SectionRow[]>([]);
  const [tab, setTab] = useState<Tab>("overview");
  const [notFound, setNotFound] = useState(false);

  const load = useCallback(async () => {
    try {
      const d = await get<AnalysisDetail>(`/analyses/${id}`);
      setA(d);
      if (d.status === "completed") setSections(await get<SectionRow[]>(`/analyses/${id}/sections`));
    } catch {
      setNotFound(true);
    }
  }, [id]);

  useEffect(() => {
    load();
  }, [load]);
  useEffect(() => {
    if (!a || a.status === "completed" || a.status === "failed") return;
    const h = setInterval(load, 1500);
    return () => clearInterval(h);
  }, [a, load]);

  if (notFound) return <Notice tone="warn">Tahlil topilmadi yoki sizga tegishli emas.</Notice>;
  if (!a) return <Spinner />;
  if (a.status === "queued" || a.status === "running") return <Progress a={a} />;
  if (a.status === "failed")
    return (
      <Card title={t.result.failed}>
        <p className="text-sm text-red-700">{a.error}</p>
        <Link href="/" className="btn-secondary mt-4">{t.common.back}</Link>
      </Card>
    );

  const reanalyze = async (depth: string) => {
    const r = await post<AnalysisSummary>(`/documents/${a.document_id}/analyses`, { depth });
    router.push(`/analyses/${r.id}`);
  };

  const tabs = Object.entries(t.result.tabs) as [Tab, string][];
  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link href="/" className="text-xs text-brand-700 hover:underline">← {t.common.back}</Link>
          <h1 className="mt-1 break-all text-xl font-semibold text-slate-900">{a.document_name}</h1>
          <div className="mt-1 flex items-center gap-2 text-xs text-slate-500">
            <StatusBadge status={a.status} /> {t.depths[a.depth]} · {a.duration_seconds?.toFixed(1)} s
            {a.version?.structure_source === "manual" && <span className="rounded bg-slate-100 px-1.5">tuzilma qo&apos;lda tuzatilgan</span>}
          </div>
        </div>
        <div className="flex flex-wrap gap-2">
          <a className="btn-primary" href={`/api/analyses/${a.id}/report?format=pdf`}>{t.result.downloadPdf}</a>
          <a className="btn-secondary" href={`/api/analyses/${a.id}/report?format=docx`}>{t.result.downloadDocx}</a>
          {a.file_available && <Link className="btn-secondary" href={`/documents/${a.document_id}/structure?analysis=${a.id}`}>{t.result.editStructure}</Link>}
          {a.file_available && (
            <select className="btn-secondary" defaultValue="" onChange={(e) => e.target.value && reanalyze(e.target.value)} aria-label={t.result.reanalyze}>
              <option value="" disabled>{t.result.reanalyze}…</option>
              {Object.entries(t.depths).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
            </select>
          )}
        </div>
      </div>

      <nav className="-mx-4 overflow-x-auto px-4" aria-label="tabs">
        <ul className="flex min-w-max gap-1 border-b border-slate-200">
          {tabs.map(([k, label]) => (
            <li key={k}>
              <button
                onClick={() => setTab(k)}
                className={`border-b-2 px-3 py-2 text-sm ${tab === k ? "border-brand-600 font-semibold text-brand-700" : "border-transparent text-slate-500 hover:text-slate-800"}`}
              >
                {label}
              </button>
            </li>
          ))}
        </ul>
      </nav>

      {tab === "overview" && a.result && (
        <div className="space-y-6">
          <OverviewPanel a={a} />
          <ChaptersCharts sections={sections} result={a.result} />
        </div>
      )}
      {tab === "chapters" && <ChaptersTable sections={sections} />}
      {tab === "passages" && <PassagesPanel analysisId={a.id} sections={sections} />}
      {tab === "similarity" && <SimilarityPanel analysisId={a.id} />}
      {tab === "academic" && <AcademicPanel a={a} />}
      {tab === "document" && <DocumentViewer documentId={a.document_id} analysisId={a.id} />}
      {tab === "method" && <MethodPanel a={a} />}
    </div>
  );
}

export default function Page() {
  return (
    <AppShell>
      <ResultView />
    </AppShell>
  );
}
