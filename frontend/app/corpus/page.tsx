"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Card, Notice, ProgressBar, Spinner } from "@/components/ui";
import { ApiError, del, get, post } from "@/lib/api";
import { bytes, date, num } from "@/lib/format";
import { t } from "@/lib/i18n";
import type { CorpusJob, CorpusStats, RefDocument, User } from "@/lib/types";

const OK_EXT = /\.(docx|pdf|txt)$/i;
const BATCH = 20;

interface HarvestSettings {
  sources: string[];
  queries: string[];
  ojs_urls: string[];
  limit: number;
  fulltext: boolean;
  core_configured: boolean;
  doc_kinds: string[];
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-3">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="text-xl font-semibold tabular-nums text-slate-900">{value}</div>
    </div>
  );
}

function CorpusView() {
  const [me, setMe] = useState<User | null>(null);
  const [stats, setStats] = useState<CorpusStats | null>(null);
  const [jobs, setJobs] = useState<CorpusJob[]>([]);
  const [docs, setDocs] = useState<{ total: number; items: RefDocument[] } | null>(null);
  const [q, setQ] = useState("");
  const [page, setPage] = useState(1);
  const [settings, setSettings] = useState<HarvestSettings | null>(null);
  const admin = !!me?.is_admin;

  const loadStats = useCallback(() => get<CorpusStats>("/corpus/stats").then(setStats).catch(() => {}), []);
  const loadJobs = useCallback(() => get<CorpusJob[]>("/corpus/jobs").then(setJobs).catch(() => {}), []);
  const loadDocs = useCallback(() => {
    const p = new URLSearchParams({ page: String(page), size: "50" });
    if (q.trim()) p.set("q", q.trim());
    return get<{ total: number; items: RefDocument[] }>(`/corpus/documents?${p}`).then(setDocs).catch(() => {});
  }, [page, q]);

  useEffect(() => {
    get<User>("/auth/me").then(setMe).catch(() => {});
    get<HarvestSettings>("/corpus/settings").then(setSettings).catch(() => {});
    loadStats();
    loadJobs();
  }, [loadStats, loadJobs]);
  useEffect(() => {
    const id = setTimeout(loadDocs, 250);
    return () => clearTimeout(id);
  }, [loadDocs]);
  useEffect(() => {
    if (!jobs.some((j) => j.status === "queued" || j.status === "running")) return;
    const id = setInterval(() => {
      loadJobs();
      loadStats();
      loadDocs();
    }, 2000);
    return () => clearInterval(id);
  }, [jobs, loadJobs, loadStats, loadDocs]);

  const refreshAll = () => {
    loadJobs();
    loadStats();
    loadDocs();
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold text-slate-900">{t.corpus.title}</h1>
        <p className="text-sm text-slate-500">{t.corpus.subtitle}</p>
      </div>
      {stats ? (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-6">
          <Stat label={t.corpus.docs} value={num(stats.documents)} />
          <Stat label={t.corpus.words} value={num(stats.words)} />
          <Stat label={t.corpus.fingerprints} value={num(stats.fingerprints)} />
          <Stat label={t.corpus.vectors} value={num(stats.vectors)} />
          <Stat label={t.corpus.size} value={stats.database_bytes ? bytes(stats.database_bytes) : "—"} />
          <Stat label={t.corpus.backend} value={stats.embedding_backend.startsWith("m2v") ? "model2vec" : "hash"} />
        </div>
      ) : <Spinner />}

      {!admin && <Notice>{t.corpus.adminOnly}</Notice>}
      {admin && (
        <div className="grid gap-6 lg:grid-cols-2">
          <UploadPanel kinds={settings?.doc_kinds ?? Object.keys(t.corpus.kinds)} onDone={refreshAll} />
          {settings && <HarvestPanel settings={settings} onStarted={refreshAll} />}
        </div>
      )}

      {jobs.length > 0 && (
        <Card title={t.corpus.jobs}>
          <ul className="space-y-3">
            {jobs.slice(0, 8).map((j) => (
              <li key={j.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="font-medium">{j.kind === "ingest" ? t.corpus.uploadTitle : t.corpus.harvestTitle} · <span className="text-slate-500">{t.status[j.status] ?? j.status}</span></span>
                  <span className="text-xs text-slate-500">{date(j.created_at)}</span>
                </div>
                {j.total > 0 && <div className="mt-2"><ProgressBar value={Math.min(100, Math.round((j.done / j.total) * 100))} /></div>}
                <div className="mt-1 text-xs text-slate-600">
                  {j.done}/{j.total || "?"} · <span className="text-emerald-700">{j.added} {t.corpus.added}</span> · {j.skipped} {t.corpus.skipped} · <span className="text-red-700">{j.failed} {t.corpus.failed}</span>
                </div>
                {j.message && <div className="mt-1 truncate text-xs text-slate-400">{j.message}</div>}
                {admin && (j.status === "queued" || j.status === "running") && (
                  <button className="mt-2 text-xs text-red-700 hover:underline" onClick={() => post(`/corpus/jobs/${j.id}/cancel`).then(loadJobs)}>{t.corpus.cancel}</button>
                )}
              </li>
            ))}
          </ul>
        </Card>
      )}

      <Card title={`${t.corpus.list} (${docs?.total ?? 0})`} actions={
        <input className="input w-64" placeholder={t.corpus.search} value={q} onChange={(e) => { setQ(e.target.value); setPage(1); }} />
      }>
        {!docs ? <Spinner /> : docs.items.length === 0 ? <p className="text-sm text-slate-500">{t.corpus.empty}</p> : (
          <>
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead>
                  <tr>
                    <th className="th">{t.plag.source}</th>
                    <th className="th">{t.corpus.kind}</th>
                    <th className="th">Manba turi</th>
                    <th className="th text-right">{t.corpus.words}</th>
                    <th className="th text-right">{t.corpus.fingerprints}</th>
                    <th className="th">{t.table.date}</th>
                    {admin && <th className="th" />}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {docs.items.map((d) => (
                    <tr key={d.id}>
                      <td className="td max-w-md">
                        <div className="font-medium text-slate-800">{d.title}</div>
                        <div className="text-xs text-slate-500">
                          {[d.authors, d.year, d.folder && `📁 ${d.folder}`, d.doi && `DOI ${d.doi}`].filter(Boolean).join(" · ")}
                          {" · "}{d.fulltext ? t.corpus.fulltextYes : t.corpus.fulltextNo}
                        </div>
                      </td>
                      <td className="td text-xs">{t.corpus.kinds[d.doc_kind] ?? d.doc_kind}</td>
                      <td className="td text-xs">{t.corpus.sources[d.source_type] ?? (d.source_type === "upload" ? "Yuklangan" : d.source_type)}</td>
                      <td className="td text-right tabular-nums">{num(d.word_count)}</td>
                      <td className="td text-right tabular-nums">{num(d.fingerprint_count)}</td>
                      <td className="td whitespace-nowrap text-xs text-slate-500">{date(d.created_at)}</td>
                      {admin && (
                        <td className="td text-right">
                          <button className="text-xs text-red-600 hover:underline" onClick={async () => {
                            if (!confirm(t.corpus.confirmDelete)) return;
                            await del(`/corpus/documents/${d.id}`);
                            refreshAll();
                          }}>{t.corpus.delete}</button>
                        </td>
                      )}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {docs.total > 50 && (
              <div className="mt-3 flex items-center gap-3 text-sm">
                <button className="btn-secondary px-3 py-1" disabled={page <= 1} onClick={() => setPage(page - 1)}>←</button>
                <span>{page} / {Math.ceil(docs.total / 50)}</span>
                <button className="btn-secondary px-3 py-1" disabled={page * 50 >= docs.total} onClick={() => setPage(page + 1)}>→</button>
              </div>
            )}
          </>
        )}
      </Card>
    </div>
  );
}

function UploadPanel({ kinds, onDone }: { kinds: string[]; onDone: () => void }) {
  const folderRef = useRef<HTMLInputElement>(null);
  const filesRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [kind, setKind] = useState("article");
  const [sent, setSent] = useState<number | null>(null);
  const [errors, setErrors] = useState<string[]>([]);

  useEffect(() => {
    folderRef.current?.setAttribute("webkitdirectory", "");
    folderRef.current?.setAttribute("directory", "");
  }, []);

  const pick = (list: FileList | null) => {
    if (!list) return;
    setFiles(Array.from(list).filter((f) => OK_EXT.test(f.name)));
  };

  const start = async () => {
    setErrors([]);
    setSent(0);
    for (let i = 0; i < files.length; i += BATCH) {
      const form = new FormData();
      files.slice(i, i + BATCH).forEach((f) => {
        form.append("files", f);
        form.append("paths", (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name);
      });
      form.append("doc_kind", kind);
      try {
        const r = await post<{ errors: { filename: string; code: string }[] }>("/corpus/upload", form);
        setErrors((e) => [...e, ...r.errors.map((x) => `${x.filename}: ${x.code}`)]);
      } catch (err) {
        setErrors((e) => [...e, err instanceof ApiError ? err.code : "error"]);
      }
      setSent(Math.min(files.length, i + BATCH));
      onDone();
    }
    setFiles([]);
    setSent(null);
  };

  return (
    <Card title={t.corpus.uploadTitle} subtitle="DOCX, PDF, TXT · darslik, maqola, dissertatsiya, avtoreferat">
      <div className="flex flex-wrap gap-2">
        <button className="btn-secondary" onClick={() => folderRef.current?.click()}>📁 {t.corpus.folder}</button>
        <button className="btn-secondary" onClick={() => filesRef.current?.click()}>{t.corpus.files}</button>
        <input ref={folderRef} type="file" multiple className="hidden" onChange={(e) => { pick(e.target.files); e.target.value = ""; }} data-testid="corpus-folder" />
        <input ref={filesRef} type="file" multiple accept=".docx,.pdf,.txt" className="hidden" onChange={(e) => { pick(e.target.files); e.target.value = ""; }} data-testid="corpus-files" />
      </div>
      {files.length > 0 && <p className="mt-2 text-sm text-slate-700">{files.length} ta fayl tanlandi ({bytes(files.reduce((a, f) => a + f.size, 0))})</p>}
      <div className="mt-3 max-w-xs">
        <label className="label" htmlFor="ckind">{t.corpus.kind}</label>
        <select id="ckind" className="input" value={kind} onChange={(e) => setKind(e.target.value)}>
          {kinds.map((k) => <option key={k} value={k}>{t.corpus.kinds[k] ?? k}</option>)}
        </select>
      </div>
      {sent !== null && (
        <div className="mt-3 space-y-1">
          <p className="text-xs text-slate-500">{t.corpus.uploading}: {sent}/{files.length}</p>
          <ProgressBar value={files.length ? (sent / files.length) * 100 : 0} />
        </div>
      )}
      {errors.length > 0 && <ul className="mt-2 max-h-32 overflow-auto text-xs text-red-700">{errors.map((e, i) => <li key={i}>{e}</li>)}</ul>}
      <button className="btn-primary mt-4" disabled={!files.length || sent !== null} onClick={start}>{t.corpus.start}</button>
    </Card>
  );
}

function HarvestPanel({ settings, onStarted }: { settings: HarvestSettings; onStarted: () => void }) {
  const [sources, setSources] = useState<string[]>(["openalex", "crossref"]);
  const [queries, setQueries] = useState(settings.queries.join("\n"));
  const [ojs, setOjs] = useState(settings.ojs_urls.join("\n"));
  const [limit, setLimit] = useState(settings.limit);
  const [fulltext, setFulltext] = useState(settings.fulltext);
  const [error, setError] = useState<string | null>(null);
  const toggle = (s: string) => setSources(sources.includes(s) ? sources.filter((x) => x !== s) : [...sources, s]);
  const start = async () => {
    setError(null);
    try {
      await post("/corpus/harvest", { sources, queries: queries.split("\n"), ojs_urls: ojs.split("\n"), limit, fulltext });
      onStarted();
    } catch (e) {
      setError(e instanceof ApiError ? e.code : "error");
    }
  };
  return (
    <Card title={t.corpus.harvestTitle} subtitle="O'zbek OJS jurnallari, CyberLeninka, OpenAlex, CORE, Crossref">
      <div className="flex flex-wrap gap-3">
        {settings.sources.map((s) => (
          <label key={s} className="flex items-center gap-1.5 text-sm">
            <input type="checkbox" checked={sources.includes(s)} onChange={() => toggle(s)} disabled={s === "core" && !settings.core_configured} />
            {t.corpus.sources[s] ?? s}
            {s === "core" && !settings.core_configured && <span className="text-xs text-slate-400">({t.corpus.coreMissing})</span>}
          </label>
        ))}
      </div>
      <div className="mt-3 grid gap-3 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="hq">{t.corpus.queries}</label>
          <textarea id="hq" className="input h-24" value={queries} onChange={(e) => setQueries(e.target.value)} />
        </div>
        <div>
          <label className="label" htmlFor="ho">{t.corpus.ojsUrls}</label>
          <textarea id="ho" className="input h-24" value={ojs} onChange={(e) => setOjs(e.target.value)} placeholder="https://jurnal.uz/index.php/nomi" />
        </div>
      </div>
      <div className="mt-3 flex flex-wrap items-end gap-4">
        <div className="w-40">
          <label className="label" htmlFor="hl">{t.corpus.limit}</label>
          <input id="hl" type="number" min={1} max={1000} className="input" value={limit} onChange={(e) => setLimit(Number(e.target.value))} />
        </div>
        <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={fulltext} onChange={(e) => setFulltext(e.target.checked)} />{t.corpus.fulltext}</label>
      </div>
      {error && <p className="mt-2 text-sm text-red-700">{error}</p>}
      <button className="btn-primary mt-4" disabled={!sources.length} onClick={start}>{t.corpus.harvest}</button>
    </Card>
  );
}

export default function Page() {
  return (
    <AppShell>
      <CorpusView />
    </AppShell>
  );
}
