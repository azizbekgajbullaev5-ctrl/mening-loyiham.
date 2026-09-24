"use client";
import { useEffect, useMemo, useState } from "react";
import { get } from "@/lib/api";
import { num } from "@/lib/format";
import { t } from "@/lib/i18n";
import { CITATION_COLOR, RESULT_COLORS, colorFor } from "@/lib/sourceColors";
import type { ContentParagraph, Plagiarism } from "@/lib/types";
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
    mods.web && `Internet (Brave): ${mods.web_stats?.queries_used ?? 0} so'rov, ${mods.web_stats?.fetched_pages ?? 0}+${mods.web_stats?.cached_pages ?? 0} sahifa, ≈$${mods.web_stats?.cost_usd ?? 0}`,
    mods.paraphrase && typeof mods.paraphrase === "object" && `Parafraz: ${mods.paraphrase.backend}`,
  ].filter(Boolean);
  const excl = Object.entries(p.exclusions).filter(([, v]) => v > 0);

  return (
    <div className="space-y-6">
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
            Internet tekshiruvida xatolar bo&apos;ldi — natija to&apos;liq bo&apos;lmasligi mumkin: {mods.web_stats!.errors.slice(0, 3).join("; ")}
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
