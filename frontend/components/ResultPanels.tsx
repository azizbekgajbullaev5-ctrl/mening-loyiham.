"use client";
import { useEffect, useMemo, useState } from "react";
import { get } from "@/lib/api";
import { band, date, num, pct } from "@/lib/format";
import { t } from "@/lib/i18n";
import type { AnalysisDetail, ContentParagraph, Passage, SectionRow, SimilarityMatch } from "@/lib/types";
import { Card, ConfidenceBadge, Notice, Spinner } from "./ui";

/* ------------------------------------------------------------------ overview */
export function OverviewPanel({ a }: { a: AnalysisDetail }) {
  const r = a.result!;
  const v = a.version;
  const b = band(r.ai.likelihood);
  const sim = r.similarity;
  const extText = sim.external !== null ? pct(sim.external, 1) : sim.scope === "local_only" ? t.result.notConfigured : t.result.notRun;
  return (
    <div className="space-y-6">
      <Card title={t.result.overview}>
        <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3 lg:grid-cols-6">
          <Info label={t.result.file} value={<span className="break-all">{a.document_name}</span>} />
          <Info label={t.table.language} value={v ? `${t.languages[v.language] ?? v.language}` : "—"} />
          <Info label={t.result.pages} value={v ? `${num(v.page_count)}${v.pages_estimated ? ` (${t.result.pagesEstimated})` : ""}` : "—"} />
          <Info label={t.result.words} value={num(v?.word_count)} />
          <Info label={t.result.chars} value={num(v?.char_count)} />
          <Info label={t.result.analyzedAt} value={date(a.finished_at)} />
        </dl>
        {v?.ocr_used && <p className="mt-3 text-xs text-amber-700">{t.result.ocr}: OCR natijalarida xatolar bo&apos;lishi mumkin.</p>}
      </Card>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card title={t.result.aiTitle} subtitle={t.result.aiSubtitle}>
          <div className="flex flex-wrap items-end gap-6">
            <div>
              <div className="text-xs text-slate-500">{t.result.overall}</div>
              <div className="text-5xl font-semibold tabular-nums text-slate-900" data-testid="ai-score">{pct(r.ai.likelihood)}</div>
              <span className={`mt-1 inline-block rounded-full px-2 py-0.5 text-xs ${b.cls}`}>{b.label}</span>
            </div>
            <div className="space-y-2 text-sm">
              <div>{t.result.confidence}: <ConfidenceBadge value={r.ai.confidence} /></div>
              <div>{t.result.flagged}: <b>{r.ai.passages_flagged}</b> / {r.ai.passages_analyzed} <span className="text-slate-500">({pct(r.ai.flagged_word_share)} {t.result.flaggedShare})</span></div>
            </div>
          </div>
          <div className="mt-4"><Notice>{r.ai.note}</Notice></div>
          <p className="mt-2 text-xs text-slate-500">{r.provider_comparison.summary_text}</p>
          {r.ai.language_note && <p className="mt-1 text-xs text-slate-500">{r.ai.language_note}</p>}
        </Card>

        <Card title={t.result.simTitle} subtitle={t.result.simSubtitle}>
          <div className="grid grid-cols-2 gap-4">
            <Stat label={t.result.simOverall} value={pct(sim.overall, 1)} big />
            <Stat label={t.result.simInternal} value={pct(sim.internal, 1)} />
            <Stat label={t.result.simCorpus} value={sim.corpus === null ? t.result.notRun : pct(sim.corpus, 1)} />
            <Stat label={t.result.simExternal} value={extText} />
          </div>
          <div className="mt-4"><Notice tone={sim.scope === "local_and_external" ? "info" : "warn"}>{sim.scope_text}</Notice></div>
          <p className="mt-2 text-xs font-medium text-slate-600">{t.result.separation}</p>
        </Card>
      </div>

      <Card title={t.result.providers}>
        <ul className="divide-y divide-slate-100 text-sm">
          {r.providers.map((p, i) => {
            const cmp = r.provider_comparison.providers.find((c) => c.name === p.name);
            return (
              <li key={`${p.name}-${i}`} className="flex flex-wrap items-center justify-between gap-2 py-2">
                <span className="font-medium text-slate-800">{p.name} <span className="text-xs font-normal text-slate-400">({p.kind}{p.category ? `, ${p.category}` : ""})</span></span>
                <span className="text-xs text-slate-600">
                  {p.status_label}
                  {p.kind === "local" && p.category !== "similarity" ? ` · ${pct(r.ai.likelihood)}` : ""}
                  {cmp?.mean_score != null ? ` · ${pct(cmp.mean_score)} (${cmp.passages_scored} parcha)` : ""}
                  {p.errors?.length ? ` · ${p.errors.join(", ")}` : ""}
                </span>
              </li>
            );
          })}
        </ul>
      </Card>
      <Notice>{r.disclaimer}</Notice>
    </div>
  );
}

function Info({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div>
      <dt className="text-xs text-slate-500">{label}</dt>
      <dd className="font-medium text-slate-900">{value}</dd>
    </div>
  );
}

function Stat({ label, value, big }: { label: string; value: string; big?: boolean }) {
  return (
    <div>
      <div className="text-xs text-slate-500">{label}</div>
      <div className={`${big ? "text-3xl" : "text-lg"} font-semibold tabular-nums text-slate-900`}>{value}</div>
    </div>
  );
}

/* ------------------------------------------------------------------ chapters */
export function ChaptersTable({ sections }: { sections: SectionRow[] }) {
  return (
    <Card title={t.result.tabs.chapters} subtitle="AI-ehtimollik va o'xshashlik — ikki alohida o'lchov">
      <div className="overflow-x-auto">
        <table className="min-w-full divide-y divide-slate-200">
          <thead>
            <tr>
              <th className="th">{t.chapters.section}</th>
              <th className="th">{t.chapters.pages}</th>
              <th className="th text-right">{t.chapters.words}</th>
              <th className="th text-right">{t.chapters.ai}</th>
              <th className="th">{t.chapters.conf}</th>
              <th className="th text-right">{t.chapters.sim}</th>
              <th className="th text-right">{t.chapters.flagged}</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {sections.filter((s) => !(s.kind === "front_matter" && s.word_count === 0)).map((s) => (
              <tr key={s.order} className={s.level === 1 ? "bg-slate-50/60" : ""}>
                <td className="td" style={{ paddingLeft: `${0.75 + (s.level - 1) * 1.25}rem` }}>
                  <span className={s.level === 1 ? "font-semibold" : ""}>{s.title || s.kind_label}</span>
                  <span className="ml-2 text-xs text-slate-400">{s.kind_label}</span>
                </td>
                <td className="td whitespace-nowrap text-xs">{s.page_start ?? "—"}–{s.page_end ?? "—"}</td>
                <td className="td text-right tabular-nums">{num(s.word_count)}</td>
                <td className="td text-right tabular-nums">{s.excluded_from_ai ? <span className="text-xs text-slate-400">{t.chapters.excluded}</span> : pct(s.ai_likelihood)}</td>
                <td className="td"><ConfidenceBadge value={s.ai_confidence} /></td>
                <td className="td text-right tabular-nums">{pct(s.similarity)}</td>
                <td className="td text-right tabular-nums">{s.suspicious_count || ""}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Card>
  );
}

/* ------------------------------------------------------------------ passages */
export function PassagesPanel({ analysisId, sections }: { analysisId: string; sections: SectionRow[] }) {
  const [items, setItems] = useState<Passage[] | null>(null);
  const [chapter, setChapter] = useState("");
  const [minScore, setMinScore] = useState(0);
  const [confidence, setConfidence] = useState("");
  const [q, setQ] = useState("");
  const chapters = sections.filter((s) => s.level === 1 && !s.excluded_from_ai);

  useEffect(() => {
    const params = new URLSearchParams();
    if (chapter) params.set("chapter", chapter);
    if (minScore) params.set("min_score", String(minScore));
    if (confidence) params.set("confidence", confidence);
    if (q.trim()) params.set("q", q.trim());
    const id = setTimeout(() => get<Passage[]>(`/analyses/${analysisId}/passages?${params}`).then(setItems).catch(() => setItems([])), 250);
    return () => clearTimeout(id);
  }, [analysisId, chapter, minScore, confidence, q]);

  return (
    <div className="space-y-4">
      <div className="card flex flex-wrap items-end gap-3 p-4">
        <div className="min-w-[10rem] flex-1">
          <label className="label" htmlFor="f-ch">{t.passages.filterChapter}</label>
          <select id="f-ch" className="input" value={chapter} onChange={(e) => setChapter(e.target.value)}>
            <option value="">{t.passages.all}</option>
            {chapters.map((c) => <option key={c.order} value={c.order}>{c.title || c.kind_label}</option>)}
          </select>
        </div>
        <div className="w-40">
          <label className="label" htmlFor="f-min">{t.passages.minScore}: {minScore}%</label>
          <input id="f-min" type="range" min={0} max={100} step={5} value={minScore} onChange={(e) => setMinScore(Number(e.target.value))} className="w-full" />
        </div>
        <div className="w-36">
          <label className="label" htmlFor="f-conf">{t.passages.confidence}</label>
          <select id="f-conf" className="input" value={confidence} onChange={(e) => setConfidence(e.target.value)}>
            <option value="">{t.passages.all}</option>
            {(["low", "medium", "high"] as const).map((c) => <option key={c} value={c}>{t.confidence[c]}</option>)}
          </select>
        </div>
        <div className="min-w-[12rem] flex-1">
          <label className="label" htmlFor="f-q">{t.passages.search}</label>
          <input id="f-q" className="input" value={q} onChange={(e) => setQ(e.target.value)} placeholder="..." />
        </div>
      </div>
      <p className="text-xs text-slate-500">{t.passages.noRewrite}</p>
      {items === null ? <Spinner /> : items.length === 0 ? <p className="text-sm text-slate-500">{t.passages.none}</p> : (
        <ul className="space-y-4">
          {items.map((p) => (
            <li key={p.id} className="card p-4" data-testid="passage">
              <div className="flex flex-wrap items-center justify-between gap-2 text-xs text-slate-500">
                <span>{t.passages.page} {p.page ?? "—"} · {t.passages.paragraph} {p.paragraph_number}{p.paragraph_end_number !== p.paragraph_number ? `–${p.paragraph_end_number}` : ""} · {p.chapter_title ?? ""}{p.section_title && p.section_title !== p.chapter_title ? ` › ${p.section_title}` : ""}</span>
                <span className="flex items-center gap-2">
                  <span className="rounded-md bg-brand-50 px-2 py-0.5 text-sm font-semibold tabular-nums text-brand-700">{pct(p.ai_likelihood)}</span>
                  <ConfidenceBadge value={p.confidence} />
                </span>
              </div>
              <blockquote className="mt-3 border-l-4 border-brand-200 bg-brand-50/40 px-3 py-2 text-sm leading-relaxed text-slate-800">{p.text}</blockquote>
              {p.characteristics.length > 0 && (
                <div className="mt-3">
                  <div className="text-xs font-semibold text-slate-600">{t.passages.characteristics}</div>
                  <ul className="mt-1 list-disc space-y-0.5 pl-5 text-sm text-slate-700">
                    {p.characteristics.map((c) => <li key={c.code}><span className="font-medium">{c.label}</span> — <span className="text-slate-500">{c.detail}</span></li>)}
                  </ul>
                </div>
              )}
              <p className="mt-2 text-xs text-slate-500"><span className="font-semibold">{t.passages.explanation}:</span> {p.explanation}</p>
              {p.provider_scores.length > 0 && (
                <div className="mt-2 text-xs text-slate-600">
                  <span className="font-semibold">{t.passages.otherProviders}:</span>{" "}
                  {p.provider_scores.map((s) => `${s.provider}: ${pct(s.score)}`).join(" · ")}
                </div>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/* ------------------------------------------------------------------ similarity */
export function SimilarityPanel({ analysisId }: { analysisId: string }) {
  const [data, setData] = useState<{ matches: SimilarityMatch[]; repeated_phrases: { phrase: string; count: number }[] } | null>(null);
  const [type, setType] = useState("");
  useEffect(() => {
    get<typeof data>(`/analyses/${analysisId}/similarity`).then(setData).catch(() => setData({ matches: [], repeated_phrases: [] }));
  }, [analysisId]);
  if (!data) return <Spinner />;
  const types = Array.from(new Set(data.matches.map((m) => m.match_type)));
  const shown = data.matches.filter((m) => !type || m.match_type === type);
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-4 lg:col-span-2">
        <Card title={t.similarity.matches} actions={
          types.length > 1 && (
            <select className="input w-auto" value={type} onChange={(e) => setType(e.target.value)}>
              <option value="">{t.passages.all}</option>
              {types.map((ty) => <option key={ty} value={ty}>{data.matches.find((m) => m.match_type === ty)?.match_type_label}</option>)}
            </select>
          )
        }>
          {shown.length === 0 ? <p className="text-sm text-slate-500">{t.similarity.none}</p> : (
            <ul className="space-y-4">
              {shown.map((m) => (
                <li key={m.id} className="rounded-lg border border-slate-200 p-3">
                  <div className="flex flex-wrap justify-between gap-2 text-xs text-slate-500">
                    <span className="font-medium text-slate-700">{m.match_type_label}</span>
                    <span className="rounded bg-emerald-50 px-2 py-0.5 font-semibold tabular-nums text-emerald-800">{pct(m.similarity)}</span>
                  </div>
                  <div className="mt-2 grid gap-3 md:grid-cols-2">
                    <div>
                      <div className="text-xs text-slate-500">{t.passages.page} {m.page ?? "—"} · {t.passages.paragraph} {m.paragraph_number ?? "—"}</div>
                      <p className="mt-1 line-clamp-6 text-sm text-slate-800">{m.text}</p>
                    </div>
                    <div>
                      <div className="text-xs text-slate-500">
                        {t.similarity.matchedWith}:{" "}
                        {m.source_title ? (m.source_url ? <a className="text-brand-700 underline" href={m.source_url} target="_blank" rel="noopener noreferrer nofollow">{m.source_title}</a> : m.source_title)
                          : m.matched_document_name ? m.matched_document_name
                          : `${t.passages.page} ${m.matched_page ?? "—"} · ${t.passages.paragraph} ${m.matched_paragraph_number ?? "—"}`}
                      </div>
                      <p className="mt-1 line-clamp-6 text-sm text-slate-600">{m.matched_text || "—"}</p>
                    </div>
                  </div>
                </li>
              ))}
            </ul>
          )}
        </Card>
      </div>
      <Card title={t.similarity.repeated}>
        {data.repeated_phrases.length === 0 ? <p className="text-sm text-slate-500">{t.similarity.none}</p> : (
          <ul className="space-y-2 text-sm">
            {data.repeated_phrases.map((p) => (
              <li key={p.phrase} className="flex justify-between gap-2">
                <span className="text-slate-700">&ldquo;{p.phrase}&rdquo;</span>
                <span className="shrink-0 text-xs text-slate-500">{p.count} {t.similarity.count}</span>
              </li>
            ))}
          </ul>
        )}
      </Card>
    </div>
  );
}

/* ------------------------------------------------------------------ academic */
export function AcademicPanel({ a }: { a: AnalysisDetail }) {
  const ac = a.result!.academic;
  const style = a.result!.style;
  return (
    <div className="grid gap-6 lg:grid-cols-3">
      <div className="space-y-6 lg:col-span-2">
        <Card title={t.academic.issues} subtitle={t.academic.note}>
          {ac.issues.length === 0 ? <p className="text-sm text-slate-500">{t.academic.noIssues}</p> : (
            <ul className="space-y-2">
              {ac.issues.map((i, k) => (
                <li key={k} className="flex gap-3 text-sm">
                  <span className={`h-fit shrink-0 rounded px-1.5 py-0.5 text-xs ${i.severity === "warning" ? "bg-amber-50 text-amber-800" : "bg-slate-100 text-slate-600"}`}>{i.severity_label}</span>
                  <span className="text-slate-700">{i.text}</span>
                </li>
              ))}
            </ul>
          )}
        </Card>
        <Card title={t.academic.components}>
          <ul className="grid gap-2 sm:grid-cols-2">
            {ac.components.map((c) => (
              <li key={c.kind} className="flex items-center justify-between rounded-md border border-slate-200 px-3 py-2 text-sm">
                <span>{c.label}</span>
                <span className={c.present ? "text-emerald-700" : "text-slate-400"}>{c.present ? `${t.academic.present} · ${num(c.word_count)}` : t.academic.missing}</span>
              </li>
            ))}
          </ul>
        </Card>
      </div>
      <div className="space-y-6">
        <Card title={t.academic.metrics}>
          <dl className="space-y-2 text-sm">
            {Object.entries(ac.metrics).map(([k, v]) => (
              <div key={k} className="flex justify-between gap-2"><dt className="text-slate-500">{t.academic.metricLabels[k] ?? k}</dt><dd className="font-medium tabular-nums">{v}</dd></div>
            ))}
          </dl>
        </Card>
        <Card title={`${t.academic.citations} / ${t.academic.references}`}>
          <dl className="space-y-2 text-sm">
            <Row k="Uslub" v={ac.citations.style} />
            <Row k="Matndagi iqtiboslar" v={ac.citations.in_text_count} />
            <Row k="Ro'yxatdagi manbalar" v={ac.references.count} />
            <Row k="Havola qilinmagan" v={ac.citations.uncited_references.length} />
            <Row k="Ro'yxatda yo'q havolalar" v={ac.citations.missing_references.length} />
            <Row k="Yillar oralig'i" v={ac.references.year_min ? `${ac.references.year_min}–${ac.references.year_max}` : "—"} />
          </dl>
        </Card>
        <Card title={t.academic.style}>
          {style.consistency === null ? <p className="text-sm text-slate-500">Bo&apos;limlar soni yoki hajmi baholash uchun yetarli emas.</p> : (
            <>
              <div className="text-2xl font-semibold tabular-nums">{style.consistency}/100</div>
              {style.shifts.map((s, i) => <p key={i} className="mt-2 text-xs text-slate-600">Uslub keskin o&apos;zgaradi: &ldquo;{s.from_title}&rdquo; → &ldquo;{s.to_title}&rdquo;</p>)}
              {style.outliers.map((o, i) => <p key={i} className="mt-2 text-xs text-slate-600">Uslubi ajralib turadi: &ldquo;{o.title}&rdquo;</p>)}
            </>
          )}
        </Card>
      </div>
    </div>
  );
}

function Row({ k, v }: { k: string; v: React.ReactNode }) {
  return <div className="flex justify-between gap-2"><dt className="text-slate-500">{k}</dt><dd className="font-medium">{v}</dd></div>;
}

/* ------------------------------------------------------------------ document viewer */
export function DocumentViewer({ documentId, analysisId }: { documentId: string; analysisId: string }) {
  const [content, setContent] = useState<{ paragraphs: ContentParagraph[]; truncated: boolean } | null>(null);
  const [flagged, setFlagged] = useState<Passage[]>([]);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    get<{ paragraphs: ContentParagraph[]; truncated: boolean }>(`/documents/${documentId}/content`).then(setContent).catch((e) => setError(e.status === 410 ? "Asl fayl o'chirilgan — hujjat ko'rinishi mavjud emas." : t.common.error));
    get<Passage[]>(`/analyses/${analysisId}/passages`).then(setFlagged).catch(() => {});
  }, [documentId, analysisId]);
  const scoreAt = useMemo(() => {
    const m = new Map<number, number>();
    for (const p of flagged) for (let i = p.paragraph_number - 1; i <= p.paragraph_end_number - 1; i++) m.set(i, Math.max(m.get(i) ?? 0, p.ai_likelihood));
    return m;
  }, [flagged]);
  if (error) return <Notice tone="warn">{error}</Notice>;
  if (!content) return <Spinner />;
  let lastPage: number | null = null;
  return (
    <Card title={t.result.tabs.document} subtitle="Ajratilgan parchalar ko'k rangda belgilangan (AI-ehtimollik chegaradan yuqori)">
      <div className="mx-auto max-w-3xl space-y-2 font-serif text-[15px] leading-relaxed">
        {content.paragraphs.map((p) => {
          const pageBreak = p.page !== null && p.page !== lastPage;
          lastPage = p.page;
          const score = scoreAt.get(p.index);
          return (
            <div key={p.index}>
              {pageBreak && <div className="my-3 border-t border-dashed border-slate-200 pt-1 text-right font-sans text-[10px] text-slate-400">{t.passages.page} {p.page}</div>}
              {p.heading ? (
                <h3 className={`font-sans font-semibold text-slate-900 ${p.heading.level === 1 ? "mt-4 text-lg" : "text-base"}`}>
                  {p.text} <span className="text-xs font-normal text-slate-400">({t.kinds[p.heading.kind] ?? p.heading.kind})</span>
                </h3>
              ) : p.kind === "table" ? (
                <pre className="overflow-x-auto whitespace-pre-wrap rounded bg-slate-50 p-2 font-sans text-xs text-slate-600">{p.text}</pre>
              ) : (
                <p className={`rounded px-1 ${score !== undefined ? "bg-brand-50 ring-1 ring-brand-200" : ""}`} title={score !== undefined ? `AI-ehtimollik: ${score.toFixed(0)}%` : undefined}>
                  <span className="mr-2 select-none font-sans text-[10px] text-slate-300">¶{p.number}</span>
                  {p.text}
                </p>
              )}
            </div>
          );
        })}
      </div>
    </Card>
  );
}

export function MethodPanel({ a }: { a: AnalysisDetail }) {
  return (
    <Card title={t.method.title}>
      <ol className="list-decimal space-y-2 pl-5 text-sm text-slate-700">
        {t.method.items.map((m) => <li key={m}>{m}</li>)}
      </ol>
      <p className="mt-4 text-xs text-slate-500">Metod versiyasi: {String(a.result?.metrics?.method_version ?? "")}</p>
      <div className="mt-4"><Notice>{a.result?.disclaimer}</Notice></div>
    </Card>
  );
}
