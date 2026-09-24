"use client";
import Link from "next/link";
import { useState } from "react";
import { ApiError, post } from "@/lib/api";
import { t } from "@/lib/i18n";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const submit = async (e: React.FormEvent) => {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "login") await post("/auth/login", { email, password });
      else await post("/auth/register", { email, password, full_name: fullName });
      window.location.href = "/";
    } catch (err) {
      const code = err instanceof ApiError ? err.code : "generic";
      setError(t.auth.errors[code] ?? (err instanceof ApiError && err.status === 422 ? t.auth.passwordHint : t.auth.errors.generic));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-gradient-to-b from-brand-50 to-white px-4">
      <div className="w-full max-w-md">
        <div className="mb-6 text-center">
          <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-xl bg-brand-600 font-bold text-white">AA</div>
          <h1 className="text-xl font-semibold text-slate-900">{t.appName}</h1>
          <p className="mt-1 text-sm text-slate-500">{t.appTagline}</p>
        </div>
        <form onSubmit={submit} className="card space-y-4 p-6">
          <h2 className="text-lg font-semibold">{mode === "login" ? t.auth.loginTitle : t.auth.registerTitle}</h2>
          {mode === "register" && (
            <div>
              <label className="label" htmlFor="name">{t.auth.fullName}</label>
              <input id="name" className="input" value={fullName} onChange={(e) => setFullName(e.target.value)} autoComplete="name" />
            </div>
          )}
          <div>
            <label className="label" htmlFor="email">{t.auth.email}</label>
            <input id="email" type="email" required className="input" value={email} onChange={(e) => setEmail(e.target.value)} autoComplete="email" />
          </div>
          <div>
            <label className="label" htmlFor="password">{t.auth.password}</label>
            <input
              id="password" type="password" required minLength={mode === "register" ? 10 : 1} className="input" value={password}
              onChange={(e) => setPassword(e.target.value)} autoComplete={mode === "login" ? "current-password" : "new-password"}
            />
            {mode === "register" && <p className="mt-1 text-xs text-slate-500">{t.auth.passwordHint}</p>}
          </div>
          {error && <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700" role="alert">{error}</p>}
          <button type="submit" className="btn-primary w-full" disabled={busy}>
            {mode === "login" ? t.auth.submitLogin : t.auth.submitRegister}
          </button>
          <p className="text-center text-sm text-slate-500">
            {mode === "login" ? t.auth.noAccount : t.auth.haveAccount}{" "}
            <Link className="font-medium text-brand-700 hover:underline" href={mode === "login" ? "/register" : "/login"}>
              {mode === "login" ? t.nav.register : t.nav.login}
            </Link>
          </p>
        </form>
      </div>
    </div>
  );
}
