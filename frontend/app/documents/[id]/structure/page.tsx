"use client";
import Link from "next/link";
import { useParams, useRouter, useSearchParams } from "next/navigation";
import { Suspense, useEffect, useState } from "react";
import { AppShell } from "@/components/AppShell";
import { Card, Notice, Spinner } from "@/components/ui";
import { get, put } from "@/lib/api";
import { t } from "@/lib/i18n";
import type { AnalysisSummary, ContentParagraph } from "@/lib/types";

interface Head { paragraph_index: number; kind: string; level: number; title: string }

const KINDS = ["title", "toc", "abstract", "keywords", "introduction", "literature_review", "methodology", "results", "discussion", "conclusion", "references", "appendix", "chapter", "section", "subsection", "heading"];
const defaultLevel = (k: string) => (k === "section" ? 2 : k === "subsection" ? 3 : 1);

function Editor() {
  const { id } = useParams<{ id: string }>();
  const search = useSearchParams();
  const router = useRouter();
  const [paras, setParas] = useState<ContentParagraph[] | null>(null);
  const [heads, setHeads] = useState<Map<number, Head>>(new Map());
  const [depth, setDepth] = useState("standard");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    Promise.all([get<{ paragraphs: ContentParagraph[] }>(`/documents/${id}/content`), get<{ headings: Head[] }>(`/documents/${id}/structure`)])
      .then(([c, s]) => {
        setParas(c.paragraphs);
        setHeads(new Map(s.headings.map((h) => [h.paragraph_index, h])));
      })
      .catch(() => setError(t.common.error));
  }, [id]);

  const setKind = (p: ContentParagraph, kind: string) => {
    const next = new Map(heads);
    if (!kind) next.delete(p.index);
    else next.set(p.index, { paragraph_index: p.index, kind, level: heads.get(p.index)?.level ?? defaultLevel(kind), title: p.text.slice(0, 300) });
    setHeads(next);
  };
  const setLevel = (idx: number, level: number) => {
    const h = heads.get(idx);
    if (!h) return;
    setHeads(new Map(heads).set(idx, { ...h, level }));
  };
  const save = async () => {
    setBusy(true);
    try {
      const r = await put<{ analysis: AnalysisSummary }>(`/documents/${id}/structure`, { headings: Array.from(heads.values()), reanalyze: true, depth });
      router.push(`/analyses/${r.analysis.id}`);
    } catch {
      setError(t.common.error);
      setBusy(false);
    }
  };

  if (error) return <Notice tone="warn">{error}</Notice>;
  if (!paras) return <Spinner />;
  return (
    <div className="space-y-4">
      <Link href={search.get("analysis") ? `/analyses/${search.get("analysis")}` : "/"} className="text-xs text-brand-700 hover:underline">← {t.structure.back}</Link>
      <Card title={t.structure.title} subtitle={t.structure.hint} actions={
        <div className="flex gap-2">
          <select className="input w-auto" value={depth} onChange={(e) => setDepth(e.target.value)}>
            {Object.entries(t.depths).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <button className="btn-primary" onClick={save} disabled={busy}>{t.structure.save}</button>
        </div>
      }>
        <ul className="divide-y divide-slate-100">
          {paras.filter((p) => p.kind !== "table").map((p) => {
            const h = heads.get(p.index);
            const short = p.text.split(/\s+/).length <= 30;
            return (
              <li key={p.index} className={`flex flex-wrap items-start gap-3 py-2 ${h ? "bg-brand-50/50" : ""}`}>
                <span className="w-10 shrink-0 pt-2 text-right text-[10px] text-slate-400">¶{p.number}</span>
                <div className="flex shrink-0 gap-2">
                  <select className="input w-44 py-1 text-xs" value={h?.kind ?? ""} onChange={(e) => setKind(p, e.target.value)} disabled={!short && !h}>
                    <option value="">{t.structure.notHeading}</option>
                    {KINDS.map((k) => <option key={k} value={k}>{t.kinds[k]}</option>)}
                  </select>
                  {h && (
                    <select className="input w-20 py-1 text-xs" value={h.level} onChange={(e) => setLevel(p.index, Number(e.target.value))} aria-label={t.structure.level}>
                      {[1, 2, 3].map((l) => <option key={l} value={l}>{l}</option>)}
                    </select>
                  )}
                </div>
                <p className={`min-w-0 flex-1 pt-1 text-sm ${h ? "font-semibold text-slate-900" : "text-slate-600"}`}>{short ? p.text : `${p.text.slice(0, 220)}…`}</p>
              </li>
            );
          })}
        </ul>
      </Card>
    </div>
  );
}

export default function Page() {
  return (
    <AppShell>
      <Suspense fallback={<Spinner />}>
        <Editor />
      </Suspense>
    </AppShell>
  );
}
