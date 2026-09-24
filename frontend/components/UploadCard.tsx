"use client";
import { useEffect, useRef, useState } from "react";
import { ApiError, get, uploadWithProgress } from "@/lib/api";
import { bytes } from "@/lib/format";
import { t } from "@/lib/i18n";
import { Card, ProgressBar } from "./ui";

const ACCEPT = ".docx,.pdf,.txt";

export function UploadCard({ onUploaded }: { onUploaded: () => void }) {
  const [files, setFiles] = useState<File[]>([]);
  const [docType, setDocType] = useState("phd_dissertation");
  const [depth, setDepth] = useState("standard");
  const [keep, setKeep] = useState(true);
  const [progress, setProgress] = useState<number | null>(null);
  const [errors, setErrors] = useState<string[]>([]);
  const [drag, setDrag] = useState(false);
  const input = useRef<HTMLInputElement>(null);
  const [maxMb, setMaxMb] = useState(50);
  useEffect(() => {
    get<{ max_upload_mb: number }>("/system/config").then((c) => setMaxMb(c.max_upload_mb)).catch(() => {});
  }, []);

  const addFiles = (list: FileList | null) => {
    if (!list) return;
    const errs: string[] = [];
    const ok = Array.from(list).filter((f) => {
      const ext = f.name.split(".").pop()?.toLowerCase();
      if (!ext || !["docx", "pdf", "txt"].includes(ext)) {
        errs.push(`${f.name}: faqat DOCX, PDF yoki TXT`);
        return false;
      }
      if (f.size > maxMb * 1024 * 1024) {
        errs.push(`${f.name}: ${maxMb} MB dan katta`);
        return false;
      }
      return true;
    });
    setErrors(errs);
    setFiles((prev) => [...prev, ...ok].slice(0, 10));
  };

  const submit = async () => {
    if (!files.length) return;
    const form = new FormData();
    files.forEach((f) => form.append("files", f));
    form.append("doc_type", docType);
    form.append("depth", depth);
    form.append("keep_for_similarity", String(keep));
    setProgress(0);
    setErrors([]);
    try {
      const res = await uploadWithProgress<{ errors: { filename: string; message: string }[] }>(form, setProgress);
      setErrors(res.errors.map((e) => `${e.filename}: ${e.message}`));
      setFiles([]);
      onUploaded();
    } catch (err) {
      const body = err instanceof ApiError ? (err.body as { errors?: { filename: string; message: string }[] } | null) : null;
      setErrors(body?.errors?.map((e) => `${e.filename}: ${e.message}`) ?? [t.common.error]);
    } finally {
      setProgress(null);
    }
  };

  return (
    <Card title={t.upload.title} subtitle={t.upload.privacy}>
      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={() => setDrag(false)}
        onDrop={(e) => { e.preventDefault(); setDrag(false); addFiles(e.dataTransfer.files); }}
        className={`flex flex-col items-center justify-center rounded-xl border-2 border-dashed px-4 py-8 text-center transition ${drag ? "border-brand-500 bg-brand-50" : "border-slate-300 bg-slate-50"}`}
      >
        <svg className="mb-2 h-8 w-8 text-brand-600" fill="none" viewBox="0 0 24 24" stroke="currentColor" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.6} d="M12 16V4m0 0l-4 4m4-4l4 4M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2" />
        </svg>
        <p className="text-sm font-medium text-slate-700">{t.upload.drop}</p>
        <p className="text-xs text-slate-500">{t.upload.formats} · {maxMb} MB gacha</p>
        <button type="button" className="btn-secondary mt-3" onClick={() => input.current?.click()}>{t.upload.choose}</button>
        <input ref={input} type="file" accept={ACCEPT} multiple className="hidden" onChange={(e) => { addFiles(e.target.files); e.target.value = ""; }} data-testid="file-input" />
      </div>

      {files.length > 0 && (
        <ul className="mt-3 divide-y divide-slate-100 rounded-lg border border-slate-200 text-sm">
          {files.map((f, i) => (
            <li key={`${f.name}-${i}`} className="flex items-center justify-between px-3 py-2">
              <span className="truncate">{f.name} <span className="text-slate-400">· {bytes(f.size)}</span></span>
              <button className="text-xs text-red-600 hover:underline" onClick={() => setFiles(files.filter((_, j) => j !== i))}>{t.table.delete}</button>
            </li>
          ))}
        </ul>
      )}

      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <div>
          <label className="label" htmlFor="doctype">{t.upload.docType}</label>
          <select id="doctype" className="input" value={docType} onChange={(e) => setDocType(e.target.value)}>
            {Object.entries(t.docTypes).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
        </div>
        <div>
          <label className="label" htmlFor="depth">{t.upload.depth}</label>
          <select id="depth" className="input" value={depth} onChange={(e) => setDepth(e.target.value)}>
            {Object.entries(t.depths).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </select>
          <p className="mt-1 text-xs text-slate-500">{t.depthHints[depth]}</p>
        </div>
      </div>
      <label className="mt-3 flex items-start gap-2 text-xs text-slate-600">
        <input type="checkbox" className="mt-0.5" checked={keep} onChange={(e) => setKeep(e.target.checked)} />
        {t.upload.keep}
      </label>

      {progress !== null && (
        <div className="mt-4 space-y-1">
          <p className="text-xs text-slate-500">{t.upload.uploading} {progress}%</p>
          <ProgressBar value={progress} />
        </div>
      )}
      {errors.length > 0 && (
        <ul className="mt-3 space-y-1 rounded-md bg-red-50 px-3 py-2 text-xs text-red-700" role="alert">
          {errors.map((e) => <li key={e}>{e}</li>)}
        </ul>
      )}
      <button className="btn-primary mt-4 w-full sm:w-auto" disabled={!files.length || progress !== null} onClick={submit}>
        {t.upload.start}
      </button>
    </Card>
  );
}
