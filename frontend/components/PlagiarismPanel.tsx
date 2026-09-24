"use client";
import { useEffect, useMemo, useState } from "react";
import { get } from "@/lib/api";
import { num } from "@/lib/format";
import { t } from "@/lib/i18n";
import { CITATION_COLOR, RESULT_COLORS, colorFor } from "@/lib/sourceColors";
import type { ContentParagraph, DuplicateDoc, Plagiarism, WebStats } from "@/lib/types";
import { Card, Notice, Spinner } from "./ui";

function ResultTiles({ p }: { p: Plagiarism }) {
  const tiles = [
    { label: t.plag.originality, value: p.originality, color: RESULT_COLORS.originality },
    { label: t.plag.borrowing, value: p.borrowing, color: RESULT_COLORS.borrowing, sub: p.paraphrase_share ? `${t.plag.paraphrase}: ${p.paraphrase_share.toFixed(2)}%` : "" },
    { label: t.plag.citation, value: p.citation, color: RESULT_COLORS.citation },
  ];
  return (
    <div>
      <div className="grid grid-cols-3 gap-3">
        {tiles.map((x) => (
          <div key={x.label} className="rounded-lg border border-slate-200 p-3">
            <div className="flex items-center gap-2 text-xs font-medium uppercase tracking-wide text-slate-500">
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: x.color }} aria-hidden />
              {x.label}
            </div>
            <div className="mt-1 text-2xl font-semibold tabular-nums text-slate-900 sm:text-3xl" data-testid={`plag-${x.label}`}>{x.value.toFixed(2)}%</div>
            {x.sub && <div className="text-xs text-slate-500">{x.sub}</div>}
          </div>
        ))}
      </div>
      <div className="mt-3 flex h-3 w-full overflow-hidden rounded-full bg-slate-100" role="img" aria-label={`${t.plag.originality} ${p.originality}%, ${t.plag.borrowing} ${p.borrowing}%, ${t.plag.citation} ${p.citation}%`}>
        <div style={{ width: `${p.originality}%`, background: RESULT_COLORS.originality }} />
        <div style={{ width: `${p.borrowing}%`, background: RESULT_COLORS.borrowing }} className="border-l-2 border-white" />
        <div style={{ width: `${p.citation}%`, background: RESULT_COLORS.citation }} className="border-l-2 border-white" />
      </div>
    </div>
  );
}

export function PlagiarismPanel({ analysisId, documentId }: { analysisId: string; documentId: string }) {
  const [p, setP] = useState<Plagiarism | null>(null);
  const [missing, setMissing] = useState(false);
  const [content, setContent] = useState<ContentParagraph[] | null>(null);
  const [contentError, setContentError] = useState(false);
  const [showText, setShowText] = useState(false);

  useEffect(() => {
    get<Plagiarism>(`/analyses/${analysisId}/plagiarism`).then(setP).catch(() => setMissing(true));
  }, [analysisId]);
  useEffect(() => {
    if (!showText || content) return;
    get<{ paragraphs: ContentParagraph[] }>(`/documents/${documentId}/content`).then((c) => setContent(c.paragraphs)).catch(() => setContentError(true));
  }, [showText, content, documentId]);

  const spansByBlock = useMemo(() => {
    const m = new Map<number, Plagiarism["spans"]>();
    for (const s of p?.spans ?? []) {
      const arr = m.get(s[0]) ?? [];
      arr.push(s);
      m.set(s[0], arr);
    }
    return m;
  }, [p]);
  const srcNumber = useMemo(() => new Map((p?.sources ?? []).map((s, i) => [s.index, i + 1])), [p]);

  if (missing) return <Notice tone="warn">{t.plag.notReady}</Notice>;
  if (!p) return <Spinner />;
  const mods = p.modules;
  const modNames = [
    mods.corpus && `${t.corpus.title} (${mods.corpus_documents ?? 0})`,
    mods.own && t.plag.ownDocs,
    mods.web && webSummary(mods.web_stats),
    mods.paraphrase && typeof mods.paraphrase === "object" && `Parafraz: ${mods.paraphrase.backend}`,
  ].filter(Boolean);
  const excl = Object.entries(p.exclusions).filter(([, v]) => v > 0);

  return (
    <div className="space-y-6">
      {mods.duplicates?.length ? <Duplicates items={mods.duplicates} /> : null}
      <Card title={t.plag.tab} subtitle={t.plag.defs}>
        <ResultTiles p={p} />
        <dl className="mt-4 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
          <div><dt className="inline font-medium">{t.plag.checkedWords}: </dt><dd className="inline">{num(p.checked_words)}</dd></div>
          <div>
            <dt className="inline font-medium">{t.plag.excluded}: </dt>
            <dd className="inline">{num(p.excluded_words)}{excl.length ? ` (${excl.map(([k, v]) => `${t.plag.exclusions[k] ?? k}: ${v}`).join(", ")})` : ""}</dd>
          </div>
          <div className="sm:col-span-2"><dt className="inline font-medium">{t.plag.modules}: </dt><dd className="inline">{modNames.join(" · ") || "—"}</dd></div>
        </dl>
        {!mods.web && <p className="mt-3 text-xs text-amber-700">{t.plag.scopeLocal}</p>}
        {mods.web && (mods.web_stats?.errors?.length ?? 0) > 0 && (
          <Notice tone="warn">
            Internet tekshiruvi to&apos;liq bo&apos;lmadi: {[...new Set(mods.web_stats!.errors.map(webError))].slice(0, 4).join(" ")}
          </Notice>
        )}
        <a className="btn-primary mt-4" href={`/api/analyses/${analysisId}/report?kind=plagiarism`}>{t.plag.report}</a>
      </Card>

      <Card title={t.plag.sources}>
        {p.sources.length === 0 ? <p className="text-sm text-slate-500">{t.plag.noSources}</p> : (
          <div className="overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead>
                <tr>
                  <th className="th">№</th>
                  <th className="th text-right">{t.plag.shareReport}</th>
                  <th className="th text-right">{t.plag.shareText}</th>
                  <th className="th">{t.plag.source}</th>
                  <th className="th">{t.plag.module}</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {p.sources.map((s, i) => (
                  <tr key={`${s.module}-${s.index}`}>
                    <td className="td"><span className="rounded px-1.5 py-0.5 text-xs font-semibold text-slate-800" style={{ background: colorFor(s.index) }}>[{i + 1}]</span></td>
                    <td className="td text-right tabular-nums">{s.share_report.toFixed(2)}%</td>
                    <td className="td text-right tabular-nums">{s.share_text.toFixed(2)}%</td>
                    <td className="td max-w-md">
                      <div className="font-medium text-slate-800">{s.title}</div>
                      <div className="text-xs text-slate-500">
                        {[s.authors, s.year].filter(Boolean).join(", ")}
                        {s.url && <> · <a className="break-all text-brand-700 underline" href={s.url} target="_blank" rel="noopener noreferrer nofollow">{s.url}</a></>}
                        {s.paraphrase_words > 0 && <> · <i>parafraz: {s.paraphrase_words} so&apos;z</i></>}
                      </div>
                    </td>
                    <td className="td text-xs">{s.module_label}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </Card>

      {mods.web && mods.web_stats && <WebPages stats={mods.web_stats} numbers={srcNumber} />}

      <Card title={t.plag.tricks}>
        {p.integrity.items.length === 0 ? <p className="text-sm text-slate-500">{t.plag.noTricks}</p> : (
          <ul className="space-y-2">
            {p.integrity.items.map((it) => (
              <li key={it.code} className={`rounded-md border px-3 py-2 text-sm ${it.severity === "high" ? "border-red-200 bg-red-50 text-red-800" : "border-amber-200 bg-amber-50 text-amber-900"}`}>
                <span aria-hidden>⚠ </span><b>{it.label}</b>: {it.count}
                {it.examples?.length ? <span className="text-xs"> — {it.examples.slice(0, 5).join(", ")}</span> : null}
                {it.pages?.length ? <span className="text-xs"> (bet: {it.pages.slice(0, 15).join(", ")})</span> : null}
              </li>
            ))}
          </ul>
        )}
      </Card>

      <Card title={t.plag.text} subtitle={t.plag.legend} actions={
        <button className="btn-secondary px-3 py-1.5" onClick={() => setShowText(!showText)}>{showText ? t.plag.hide : t.plag.show}</button>
      }>
        {!showText ? <p className="text-sm text-slate-500">{t.plag.showHint}</p>
          : contentError ? <Notice tone="warn">Asl fayl o&apos;chirilgan — matn ko&apos;rinishi mavjud emas.</Notice>
          : !content ? <Spinner /> : (
            <div className="mx-auto max-w-3xl space-y-2 font-serif text-[15px] leading-relaxed" data-testid="plag-text">
              {content.filter((c) => c.kind !== "table").map((c) => (
                <p key={c.index} className={c.heading ? "font-sans font-semibold" : ""}>
                  <Highlighted text={c.text} spans={spansByBlock.get(c.index) ?? []} numbers={srcNumber} />
                </p>
              ))}
            </div>
          )}
      </Card>
    </div>
  );
}

function webSummary(w?: WebStats): string {
  if (!w) return "Internet (Brave)";
  const parts = [`${w.queries_used} so'rov`];
  if (w.results_total !== undefined) parts.push(`${w.results_total} natija`);
  parts.push(`${w.fetched_pages} yuklandi`, `${w.cached_pages} keshdan`);
  if (w.failed_pages) parts.push(`${w.failed_pages} yuklanmadi`);
  return `Internet (Brave): ${parts.join(", ")}, ≈$${w.cost_usd ?? 0}`;
}

function webError(e: string): string {
  const code = e.split(/[:\s]/)[0];
  const key = code.startsWith("brave_auth") ? "brave_auth" : code;
  return t.plag.webErrors[key] ?? e;
}

function Duplicates({ items }: { items: DuplicateDoc[] }) {
  const excluded = items.filter((d) => d.excluded);
  const nameOnly = items.filter((d) => !d.excluded);
  const row = (d: DuplicateDoc) => (
    <li key={d.id}>
      <b>{d.filename}</b>
      {d.uploaded_at && <> — {new Date(d.uploaded_at).toLocaleString("uz-UZ")}</>}
      {" "}({d.reasons.map((r) => t.plag.dupReasons[r] ?? r).join(", ")}
      {d.overlap != null && `, matn mosligi ${Math.round(d.overlap * 100)}%`})
    </li>
  );
  return (
    <Notice tone="warn">
      {excluded.length > 0 && (
        <div data-testid="dup-warning">
          <b>{t.plag.dupTitle}.</b> {t.plag.dupExcluded}
          <ul className="ml-5 mt-1 list-disc">{excluded.map(row)}</ul>
        </div>
      )}
      {nameOnly.length > 0 && (
        <div className={excluded.length ? "mt-2" : ""}>
          {t.plag.dupNameOnly}
          <ul className="ml-5 mt-1 list-disc">{nameOnly.map(row)}</ul>
        </div>
      )}
    </Notice>
  );
}

function WebPages({ stats, numbers }: { stats: WebStats; numbers: Map<number, number> }) {
  const [showQueries, setShowQueries] = useState(false);
  const pages = [...(stats.pages ?? [])].sort((a, b) => Number(b.source_index != null) - Number(a.source_index != null) || Number(b.status === "ok") - Number(a.status === "ok"));
  return (
    <Card title={t.plag.webPages} subtitle={t.plag.webPagesHint} actions={
      stats.query_log?.length ? <button className="btn-secondary px-3 py-1.5" onClick={() => setShowQueries(!showQueries)}>{t.plag.webQueries} ({stats.query_log.length})</button> : undefined
    }>
      {showQueries && stats.query_log && (
        <ol className="mb-4 ml-5 list-decimal space-y-1 text-xs text-slate-600">
          {stats.query_log.map((q, i) => (
            <li key={i}>{q.q} — <span className={q.results ? "text-slate-800" : "text-amber-700"}>{q.results == null ? `xato: ${q.error ?? ""}` : `${q.results} natija`}</span></li>
          ))}
        </ol>
      )}
      {pages.length === 0 ? <p className="text-sm text-slate-500">{t.plag.webNoPages}</p> : (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm" data-testid="web-pages">
            <thead>
              <tr><th className="th">Sahifa</th><th className="th">Holat</th><th className="th">Natija</th></tr>
            </thead>
            <tbody className="divide-y divide-slate-100">
              {pages.map((pg) => {
                const n = pg.source_index != null ? numbers.get(pg.source_index) : undefined;
                return (
                  <tr key={pg.url}>
                    <td className="td max-w-md">
                      <div className="truncate font-medium text-slate-800">{pg.title || pg.url}</div>
                      <a className="break-all text-xs text-brand-700 underline" href={pg.url} target="_blank" rel="noopener noreferrer nofollow">{pg.url}</a>
                    </td>
                    <td className={`td text-xs ${pg.status === "ok" ? "text-slate-700" : "text-amber-700"}`}>
                      {t.plag.pageStatus[pg.status] ?? (pg.status.startsWith("http_") ? `server javobi ${pg.status.slice(5)}` : pg.status)}
                      {pg.cached && " (keshdan)"}
                      {pg.status === "ok" && pg.words > 0 && <span className="text-slate-500"> · {num(pg.words)} so&apos;z</span>}
                    </td>
                    <td className="td text-xs">
                      {n ? <span className="rounded px-1.5 py-0.5 font-semibold text-slate-800" style={{ background: colorFor(pg.source_index!) }}>manba [{n}]</span>
                        : pg.status === "ok" ? "moslik yo'q" : "—"}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

function Highlighted({ text, spans, numbers }: { text: string; spans: Plagiarism["spans"]; numbers: Map<number, number> }) {
  const parts: React.ReactNode[] = [];
  let pos = 0;
  [...spans].sort((a, b) => a[1] - b[1]).forEach((s, k) => {
    const [, start, end, src, cls] = s;
    if (start < pos) return;
    if (start > pos) parts.push(text.slice(pos, start));
    const frag = text.slice(start, end);
    if (cls === "c") {
      parts.push(<mark key={k} style={{ background: CITATION_COLOR }} title="Iqtibos">{frag}</mark>);
    } else {
      const n = numbers.get(src);
      parts.push(
        <mark key={k} style={{ background: colorFor(src) }} className={cls === "p" ? "italic" : ""} title={n ? `Manba [${n}]${cls === "p" ? " — parafraz" : ""}` : undefined}>
          {n && <sup className="mr-0.5 font-sans text-[9px] font-semibold text-slate-700">[{n}]</sup>}
          {frag}
        </mark>,
      );
    }
    pos = end;
  });
  parts.push(text.slice(pos));
  return <>{parts}</>;
}
