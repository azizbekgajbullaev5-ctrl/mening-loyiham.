"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import { post } from "@/lib/api";
import { t } from "@/lib/i18n";
import { useUser } from "@/lib/useUser";
import { Spinner } from "./ui";

export function AppShell({ children }: { children: ReactNode }) {
  const { user, loading } = useUser();
  const logout = async () => {
    await post("/auth/logout");
    window.location.href = "/login";
  };
  return (
    <div className="min-h-screen">
      <header className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-3 px-4 py-3">
          <Link href="/" className="flex items-center gap-3">
            <span className="flex h-9 w-9 items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white" aria-hidden>
              AA
            </span>
            <span>
              <span className="block text-sm font-semibold text-slate-900 sm:text-base">{t.appName}</span>
              <span className="hidden text-xs text-slate-500 sm:block">Academic AI &amp; Similarity Analyzer</span>
            </span>
          </Link>
          <nav className="flex items-center gap-3 text-sm">
            {user && (
              <>
                <Link href="/" className="text-slate-600 hover:text-brand-700">{t.nav.dashboard}</Link>
                <Link href="/corpus/" className="text-slate-600 hover:text-brand-700">{t.corpus.nav}</Link>
                <span className="hidden text-slate-400 md:inline">{user.email}</span>
                <button onClick={logout} className="btn-secondary px-3 py-1.5">{t.nav.logout}</button>
              </>
            )}
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-7xl px-4 py-6">{loading ? <Spinner /> : user ? children : <Spinner />}</main>
      <footer className="mx-auto max-w-7xl px-4 pb-8 text-xs text-slate-400">
        AI-ehtimollik natijalari ehtimoliy ko&apos;rsatkichlardir va AI mualliflikning qat&apos;iy isboti emas.
      </footer>
    </div>
  );
}
