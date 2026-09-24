"use client";
import Link from "next/link";
import { del } from "@/lib/api";
import { date, num, pct } from "@/lib/format";
import { t } from "@/lib/i18n";
import type { AnalysisSummary } from "@/lib/types";
import { Card, ConfidenceBadge, StatusBadge } from "./ui";

export function AnalysesTable({ items, onChanged }: { items: AnalysisSummary[]; onChanged: () => void }) {
  const remove = async (docId: string) => {
    if (!confirm(t.table.confirmDelete)) return;
    await del(`/documents/${docId}`);
    onChanged();
  };
  return (
    <Card title={t.table.recent} subtitle="AI-ehtimollik — baho, isbot emas · O'xshashlik — alohida o'lchov">
      {items.length === 0 ? (
        <p className="text-sm text-slate-500">{t.table.empty}</p>
      ) : (
        <>
          {/* desktop / tablet */}
          <div className="hidden overflow-x-auto md:block">
            <table className="min-w-full divide-y divide-slate-200">
              <thead>
                <tr>
                  <th className="th">{t.table.document}</th>
                  <th className="th">{t.table.language}</th>
                  <th className="th text-right">{t.table.words}</th>
                  <th className="th text-right">{t.table.ai}</th>
                  <th className="th text-right">{t.table.similarity}</th>
                  <th className="th">{t.table.status}</th>
                  <th className="th">{t.table.date}</th>
                  <th className="th" />
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {items.map((a) => (
                  <tr key={a.id} className="hover:bg-slate-50">
                    <td className="td max-w-xs">
                      <Link href={`/analyses/${a.id}`} className="font-medium text-brand-700 hover:underline">{a.document_name}</Link>
                      <div className="text-xs text-slate-400">{t.docTypes[a.doc_type ?? ""] ?? ""} · {t.depths[a.depth]}</div>
                    </td>
                    <td className="td">{a.language ? t.languages[a.language] ?? a.language : "—"}</td>
                    <td className="td text-right tabular-nums">{num(a.word_count)}</td>
                    <td className="td text-right">
                      <span className="tabular-nums">{pct(a.ai_likelihood)}</span>
                      {a.ai_confidence && <div className="mt-0.5"><ConfidenceBadge value={a.ai_confidence} /></div>}
                    </td>
                    <td className="td text-right tabular-nums">{pct(a.similarity_overall)}</td>
                    <td className="td"><StatusBadge status={a.status} progress={a.progress} /></td>
                    <td className="td whitespace-nowrap text-xs text-slate-500">{date(a.created_at)}</td>
                    <td className="td whitespace-nowrap text-right">
                      <Link href={`/analyses/${a.id}`} className="mr-3 text-xs text-brand-700 hover:underline">{t.table.open}</Link>
                      <button onClick={() => remove(a.document_id)} className="text-xs text-red-600 hover:underline">{t.table.delete}</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          {/* mobile */}
          <ul className="space-y-3 md:hidden">
            {items.map((a) => (
              <li key={a.id} className="rounded-lg border border-slate-200 p-3">
                <div className="flex items-start justify-between gap-2">
                  <Link href={`/analyses/${a.id}`} className="font-medium text-brand-700">{a.document_name}</Link>
                  <StatusBadge status={a.status} progress={a.progress} />
                </div>
                <dl className="mt-2 grid grid-cols-3 gap-2 text-xs">
                  <div><dt className="text-slate-400">{t.table.ai}</dt><dd className="font-semibold">{pct(a.ai_likelihood)}</dd></div>
                  <div><dt className="text-slate-400">{t.table.similarity}</dt><dd className="font-semibold">{pct(a.similarity_overall)}</dd></div>
                  <div><dt className="text-slate-400">{t.table.words}</dt><dd>{num(a.word_count)}</dd></div>
                </dl>
                <button onClick={() => remove(a.document_id)} className="mt-2 text-xs text-red-600">{t.table.delete}</button>
              </li>
            ))}
          </ul>
        </>
      )}
    </Card>
  );
}
