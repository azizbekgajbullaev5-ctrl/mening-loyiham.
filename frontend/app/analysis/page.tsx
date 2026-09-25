"use client";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Suspense, useCallback, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { ChaptersCharts } from "@/components/Charts";
import { PlagiarismPanel } from "@/components/PlagiarismPanel";
import { ModulePicker, estimateTotals } from "@/components/ModulePicker";
import { AcademicPanel, ChaptersTable, DocumentViewer, MethodPanel, OverviewPanel, PassagesPanel, SimilarityPanel } from "@/components/ResultPanels";
import { Card, Notice, ProgressBar, Spinner, StatusBadge } from "@/components/ui";
import { get, post } from "@/lib/api";
import { analysisHref, structureHref } from "@/lib/links";
import { t } from "@/lib/i18n";
import type { AnalysisDetail, AnalysisSummary, SectionRow } from "@/lib/types";

type Tab = keyof typeof t.result.tabs;

function Progress({ a }: { a: AnalysisDetail }) {
  const msg = a.message === "checkpoint" ? t.result.resumedFromCheckpoint : a.message.startsWith("retry") ? t.result.retrying : a.message === "resume" ? "" : a.message;
  return (
    <Card title={a.document_name ?? ""} subtitle={`${t.depths[a.depth]} · ${t.status[a.status]}`}>
      <div className="space-y-3">
        {a.status === "queued" && a.queue_position !== null && (
          <Notice>
            {t.result.queuePosition}: <b>{a.queue_position}</b>. {t.result.queueHint}
          </Notice>
        )}
        <div className="flex items-center justify-between text-sm">
          <span className="font-medium text-slate-700">{t.stages[a.stage] ?? a.stage}{msg ? `: ${msg}` : ""}</span>
          <span className="tabular-nums text-slate-500">{a.progress}%</span>
        </div>
        <ProgressBar value={a.progress} />
        <ol className="grid gap-1 text-xs text-slate-500 sm:grid-cols-3">
          {["extracting", "language", "segmenting", "ai_analysis", "similarity", "plagiarism", "style", "academic", "aggregating"].map((s) => (
            <li key={s} className={a.stage === s ? "font-semibold text-brand-700" : ""}>• {t.stages[s]}</li>
          ))}
        </ol>
      </div>
    </Card>
  );
}

function ModulesConfirm({ a, onDone }: { a: AnalysisDetail; onDone: () => void }) {
  const e = a.web_estimate!;
  const mods = Object.values(e.modules ?? {});
  const [selected, setSelected] = useState<string[]>(a.check_modules ?? e.selected ?? []);
  const [busy, setBusy] = useState(false);
  const tot = estimateTotals(mods, selected);
  const go = async (keys: string[]) => {
    setBusy(true);
    await post(`/analyses/${a.id}/confirm`, { modules: keys });
    onDone();
  };
  const local = selected.filter((k) => e.modules?.[k]?.kind === "local");
  return (
    <Card title={t.modules.confirmTitle} subtitle={a.document_name ?? ""}>
      <dl className="mb-4 grid gap-4 sm:grid-cols-4">
        <div><dt className="text-xs text-slate-500">{t.result.words}</dt><dd className="text-xl font-semibold tabular-nums">{e.words.toLocaleString("uz-UZ")}</dd></div>
        <div><dt className="text-xs text-slate-500">{t.modules.requests}</dt><dd className="text-xl font-semibold tabular-nums">{tot.requests}</dd></div>
        <div><dt className="text-xs text-slate-500">{t.modules.time}</dt><dd className="text-xl font-semibold tabular-nums">≈ {Math.max(1, Math.round(tot.seconds / 60))} daq</dd></div>
        <div><dt className="text-xs text-slate-500">{t.modules.cost}</dt>
          <dd className="text-xl font-semibold tabular-nums" data-testid="total-cost">{tot.cost > 0 ? `≈ $${tot.cost.toFixed(3)}` : "bepul"}</dd>
          <dd className="text-xs text-slate-500">Brave: ${e.price_per_1000_usd} / 1000 so&apos;rov</dd></div>
      </dl>
      <p className="mb-3 text-xs text-slate-500">{t.modules.confirmHint} {e.note}</p>
      <ModulePicker modules={mods} selected={selected} onChange={setSelected} showEstimate />
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="btn-primary" disabled={busy} onClick={() => go(selected)} data-testid="confirm-modules">{t.modules.start}</button>
        <button className="btn-secondary" disabled={busy} onClick={() => go(local)}>{t.modules.localOnly}</button>
      </div>
    </Card>
  );
}

function WebConfirm({ a, onDone }: { a: AnalysisDetail; onDone: () => void }) {
  const e = a.web_estimate;
  const [busy, setBusy] = useState(false);
  const go = async (web: boolean) => {
    setBusy(true);
    await post(`/analyses/${a.id}/confirm`, { web_check: web });
    onDone();
  };
  return (
    <Card title={t.web.confirmTitle} subtitle={a.document_name ?? ""}>
      {e ? (
        <dl className="grid gap-4 sm:grid-cols-4">
          <div><dt className="text-xs text-slate-500">{t.result.words}</dt><dd className="text-xl font-semibold tabular-nums">{e.words.toLocaleString("uz-UZ")}</dd></div>
          <div><dt className="text-xs text-slate-500">{t.web.queries}</dt><dd className="text-xl font-semibold tabular-nums">{e.queries}</dd></div>
          <div><dt className="text-xs text-slate-500">{t.web.pages}</dt><dd className="text-xl font-semibold tabular-nums">{e.max_pages}</dd></div>
          <div><dt className="text-xs text-slate-500">{t.web.cost}</dt><dd className="text-xl font-semibold tabular-nums">≈ ${e.cost_usd.toFixed(3)}</dd>
            <dd className="text-xs text-slate-500">{t.web.price}: ${e.price_per_1000_usd}</dd></div>
        </dl>
      ) : null}
      <p className="mt-3 text-xs text-slate-500">{t.web.note}</p>
      {e && !e.configured && <div className="mt-3"><Notice tone="warn">{t.web.notConfigured}</Notice></div>}
      <div className="mt-4 flex flex-wrap gap-2">
        <button className="btn-primary" disabled={busy || !e?.configured} onClick={() => go(true)}>{t.web.confirm}</button>
        <button className="btn-secondary" disabled={busy} onClick={() => go(false)}>{t.web.skip}</button>
      </div>
    </Card>
  );
}

function ResultView() {
  const id = useSearchParams().get("id") ?? "";
  const router = useRouter();
  const [a, setA] = useState<AnalysisDetail | null>(null);
  const [sections, setSections] = useState<SectionRow[]>([]);
  const [tab, setTab] = useState<Tab>("plagiarism");
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
  if (a.status === "awaiting_confirmation")
    return a.web_estimate?.modules ? <ModulesConfirm a={a} onDone={load} /> : <WebConfirm a={a} onDone={load} />;
  if (a.status === "queued" || a.status === "running") return <Progress a={a} />;
  if (a.status === "failed") {
    const code = (a.error ?? "").split(":")[0];
    const resume = async () => {
      await post(`/analyses/${a.id}/resume`);
      load();
    };
    return (
      <Card title={t.result.failed} subtitle={a.document_name ?? ""}>
        <p className="text-sm text-red-700">{t.errors[code] ?? t.common.error}</p>
        <p className="mt-1 text-xs text-slate-400">{a.error}</p>
        <div className="mt-4 flex flex-wrap gap-2">
          {a.file_available && <button className="btn-primary" onClick={resume}>{t.result.resume}</button>}
          <Link href="/" className="btn-secondary">{t.common.back}</Link>
        </div>
        {a.file_available && <p className="mt-2 text-xs text-slate-500">{t.result.resumeHint}</p>}
      </Card>
    );
  }

  const reanalyze = async (depth: string) => {
    const r = await post<AnalysisSummary>(`/documents/${a.document_id}/analyses`, { depth });
    router.push(analysisHref(r.id));
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
          {a.file_available && <Link className="btn-secondary" href={structureHref(a.document_id, a.id)}>{t.result.editStructure}</Link>}
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

      {tab === "plagiarism" && <PlagiarismPanel analysisId={a.id} documentId={a.document_id} />}
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
      <Suspense fallback={<Spinner />}>
        <ResultView />
      </Suspense>
    </AppShell>
  );
}
