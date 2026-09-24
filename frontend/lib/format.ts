export const pct = (v: number | null | undefined, digits = 0) => (v === null || v === undefined ? "—" : `${v.toFixed(digits)}%`);

export const num = (v: number | null | undefined) => (v === null || v === undefined ? "—" : v.toLocaleString("uz-UZ").replace(/,/g, " "));

export const date = (iso: string | null | undefined) => {
  if (!iso) return "—";
  const d = new Date(iso);
  return `${d.toLocaleDateString("uz-UZ")} ${d.toLocaleTimeString("uz-UZ", { hour: "2-digit", minute: "2-digit" })}`;
};

export const bytes = (n: number) => (n < 1024 * 1024 ? `${(n / 1024).toFixed(0)} KB` : `${(n / 1024 / 1024).toFixed(1)} MB`);

/** Qualitative band for an AI-likelihood estimate (wording avoids certainty). */
export function band(v: number | null | undefined): { label: string; cls: string } {
  if (v === null || v === undefined) return { label: "—", cls: "bg-slate-100 text-slate-600" };
  if (v >= 70) return { label: "AI-ga xos belgilar ko'p", cls: "bg-brand-100 text-brand-900" };
  if (v >= 50) return { label: "Aralash belgilar", cls: "bg-brand-50 text-brand-700" };
  return { label: "AI-ga xos belgilar kam", cls: "bg-slate-100 text-slate-700" };
}
