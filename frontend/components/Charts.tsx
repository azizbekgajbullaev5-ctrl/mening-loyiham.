"use client";
/**
 * Charts follow a restrained academic style: one series per chart, fixed
 * 0–100 axes for percentages (no zoomed axes that exaggerate differences),
 * hairline grids, thin bars with 4px rounded data-ends, text in ink colours,
 * hover tooltips, and a table view for every chart.
 */
import { useState, type ReactNode } from "react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Scatter,
  ScatterChart,
  Tooltip,
  XAxis,
  YAxis,
  ZAxis,
} from "recharts";
import { num, pct } from "@/lib/format";
import { t } from "@/lib/i18n";
import type { AnalysisResult, SectionRow } from "@/lib/types";

const C = {
  ai: "#2a78d6",
  sim: "#1baf7a",
  neutral: "#9ca3af",
  grid: "#e1e0d9",
  axis: "#c3c2b7",
  muted: "#898781",
  ink2: "#52514e",
  surface: "#ffffff",
};
const tick = { fill: C.muted, fontSize: 11 };

function ChartCard({ title, note, table, children }: { title: string; note?: string; table: ReactNode; children: ReactNode }) {
  const [showTable, setShowTable] = useState(false);
  return (
    <figure className="card p-4">
      <figcaption className="mb-2 flex items-start justify-between gap-2">
        <div>
          <div className="text-sm font-semibold text-slate-900">{title}</div>
          {note && <div className="text-xs text-slate-500">{note}</div>}
        </div>
        <button className="shrink-0 text-xs text-brand-700 hover:underline" onClick={() => setShowTable(!showTable)}>
          {showTable ? t.charts.hideTable : t.charts.showTable}
        </button>
      </figcaption>
      {showTable ? <div className="max-h-64 overflow-auto">{table}</div> : <div className="h-60">{children}</div>}
    </figure>
  );
}

function TipBox({ children }: { children: ReactNode }) {
  return <div className="rounded-md border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 shadow-sm">{children}</div>;
}

function SimpleTable({ head, rows }: { head: string[]; rows: (string | number)[][] }) {
  return (
    <table className="min-w-full text-xs">
      <thead>
        <tr>{head.map((h) => <th key={h} className="th">{h}</th>)}</tr>
      </thead>
      <tbody className="divide-y divide-slate-100">
        {rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className="td text-xs">{c}</td>)}</tr>)}
      </tbody>
    </table>
  );
}

const shortTitle = (s: SectionRow) => {
  const m = s.title.match(/^\s*([IVXLC]+|\d+)[\s.-]*(bob|глава|chapter)?/i) || s.title.match(/(глава|chapter)\s+([IVXLC]+|\d+)/i);
  if (s.kind === "chapter" && m) return m[0].trim().replace(/\.$/, "");
  const label = s.title || s.kind_label;
  return label.length > 13 ? `${label.slice(0, 12)}…` : label;
};

export function ChaptersCharts({ sections, result }: { sections: SectionRow[]; result: AnalysisResult }) {
  const top = sections.filter((s) => s.level === 1 && s.kind !== "front_matter" && s.kind !== "title" && s.word_count > 0);
  const scored = top.filter((s) => s.ai_likelihood !== null);
  const aiData = scored.map((s) => ({ name: shortTitle(s), full: s.title, value: s.ai_likelihood, conf: s.ai_confidence_label }));
  const simData = top.filter((s) => s.similarity !== null).map((s) => ({ name: shortTitle(s), full: s.title, value: s.similarity }));
  const wordData = top.map((s) => ({ name: shortTitle(s), full: s.title, value: s.word_count }));
  const dist = result.score_distribution.map((d) => ({ name: d.range, value: d.count }));
  const threshold = result.ai.threshold ?? 60;
  const positions = result.passage_positions.map((p) => ({ x: Math.round(p.pos * 1000) / 10, y: p.score, page: p.page, flagged: p.flagged }));

  const pctBars = (data: { name: string; full: string; value: number | null; conf?: string | null }[], color: string, withThreshold: boolean) => (
    <ResponsiveContainer width="100%" height="100%">
      <BarChart data={data} margin={{ top: 8, right: 8, left: -12, bottom: 4 }} barCategoryGap="30%">
        <CartesianGrid vertical={false} stroke={C.grid} strokeWidth={1} />
        <XAxis dataKey="name" tick={tick} tickLine={false} axisLine={{ stroke: C.axis }} interval={0} />
        <YAxis domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} tick={tick} tickLine={false} axisLine={false} unit="%" />
        {withThreshold && <ReferenceLine y={threshold} stroke={C.ink2} strokeWidth={1} label={{ value: t.charts.threshold, position: "insideTopRight", fill: C.muted, fontSize: 10 }} />}
        <Tooltip
          cursor={{ fill: "rgba(42,120,214,0.06)" }}
          content={({ active, payload }) =>
            active && payload?.length ? (
              <TipBox>
                <div className="font-medium">{payload[0].payload.full}</div>
                <div>{pct(payload[0].value as number, 1)}{payload[0].payload.conf ? ` · ${t.result.confidence}: ${payload[0].payload.conf}` : ""}</div>
              </TipBox>
            ) : null
          }
        />
        <Bar dataKey="value" fill={color} maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false} />
      </BarChart>
    </ResponsiveContainer>
  );

  return (
    <div className="grid gap-4 md:grid-cols-2">
      <ChartCard
        title={t.charts.aiByChapter}
        note={t.charts.estimateNote}
        table={<SimpleTable head={[t.chapters.section, t.chapters.ai, t.chapters.conf]} rows={scored.map((s) => [s.title, pct(s.ai_likelihood, 1), s.ai_confidence_label ?? "—"])} />}
      >
        {pctBars(aiData, C.ai, true)}
      </ChartCard>
      <ChartCard
        title={t.charts.simByChapter}
        note={result.similarity.scope_text}
        table={<SimpleTable head={[t.chapters.section, t.chapters.sim]} rows={simData.map((s) => [s.full, pct(s.value, 1)])} />}
      >
        {pctBars(simData, C.sim, false)}
      </ChartCard>
      <ChartCard
        title={t.charts.distribution}
        note={`${result.ai.passages_analyzed} ${t.charts.passagesCount}`}
        table={<SimpleTable head={[t.chapters.ai, t.charts.passagesCount]} rows={dist.map((d) => [d.name, d.value])} />}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={dist} margin={{ top: 8, right: 8, left: -18, bottom: 4 }} barCategoryGap={2}>
            <CartesianGrid vertical={false} stroke={C.grid} />
            <XAxis dataKey="name" tick={{ ...tick, fontSize: 10 }} tickLine={false} axisLine={{ stroke: C.axis }} />
            <YAxis allowDecimals={false} tick={tick} tickLine={false} axisLine={false} />
            <Tooltip
              cursor={{ fill: "rgba(42,120,214,0.06)" }}
              content={({ active, payload }) =>
                active && payload?.length ? <TipBox>{payload[0].payload.name}: {payload[0].value} {t.charts.passagesCount}</TipBox> : null
              }
            />
            <Bar dataKey="value" maxBarSize={24} radius={[4, 4, 0, 0]} isAnimationActive={false}>
              {dist.map((d, i) => <Cell key={d.name} fill={i * 10 >= threshold ? C.ai : C.neutral} />)}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
      <ChartCard
        title={t.charts.positions}
        note={`${t.charts.position}: 0% = boshi, 100% = oxiri`}
        table={<SimpleTable head={[t.charts.position, t.passages.page, t.chapters.ai]} rows={positions.filter((p) => p.flagged).map((p) => [`${p.x}%`, p.page ?? "—", pct(p.y, 1)])} />}
      >
        <div className="flex h-full flex-col">
          <div className="mb-1 flex gap-4 text-xs text-slate-600" aria-hidden>
            <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full" style={{ background: C.ai }} />{t.charts.flagged}</span>
            <span className="flex items-center gap-1"><span className="inline-block h-2 w-2 rounded-full" style={{ background: C.neutral }} />{t.charts.notFlagged}</span>
          </div>
          <div className="min-h-0 flex-1">
            <ResponsiveContainer width="100%" height="100%">
              <ScatterChart margin={{ top: 8, right: 12, left: -12, bottom: 4 }}>
                <CartesianGrid stroke={C.grid} />
                <XAxis type="number" dataKey="x" domain={[0, 100]} ticks={[0, 25, 50, 75, 100]} unit="%" tick={tick} tickLine={false} axisLine={{ stroke: C.axis }} />
                <YAxis type="number" dataKey="y" domain={[0, 100]} ticks={[0, 50, 100]} unit="%" tick={tick} tickLine={false} axisLine={false} />
                <ZAxis range={[40, 40]} />
                <ReferenceLine y={threshold} stroke={C.ink2} strokeWidth={1} />
                <Tooltip
                  content={({ active, payload }) =>
                    active && payload?.length ? (
                      <TipBox>
                        {t.passages.page}: {payload[0].payload.page ?? "—"} · {t.chapters.ai}: {pct(payload[0].payload.y, 1)}
                      </TipBox>
                    ) : null
                  }
                />
                <Scatter data={positions} isAnimationActive={false}>
                  {positions.map((p, i) => <Cell key={i} fill={p.flagged ? C.ai : C.neutral} stroke={C.surface} strokeWidth={2} />)}
                </Scatter>
              </ScatterChart>
            </ResponsiveContainer>
          </div>
        </div>
      </ChartCard>
      <ChartCard
        title={t.charts.wordsByChapter}
        table={<SimpleTable head={[t.chapters.section, t.chapters.words]} rows={wordData.map((w) => [w.full, num(w.value)])} />}
      >
        <ResponsiveContainer width="100%" height="100%">
          <BarChart data={wordData} layout="vertical" margin={{ top: 4, right: 16, left: 8, bottom: 4 }} barCategoryGap="30%">
            <CartesianGrid horizontal={false} stroke={C.grid} />
            <XAxis type="number" tick={tick} tickLine={false} axisLine={false} />
            <YAxis type="category" dataKey="name" width={104} tick={tick} tickLine={false} axisLine={{ stroke: C.axis }} />
            <Tooltip
              cursor={{ fill: "rgba(0,0,0,0.04)" }}
              content={({ active, payload }) => (active && payload?.length ? <TipBox>{payload[0].payload.full}: {num(payload[0].value as number)}</TipBox> : null)}
            />
            <Bar dataKey="value" fill={C.neutral} maxBarSize={20} radius={[0, 4, 4, 0]} isAnimationActive={false} />
          </BarChart>
        </ResponsiveContainer>
      </ChartCard>
    </div>
  );
}
