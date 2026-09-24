/**
 * Thin fetch wrapper. All requests go to the same origin (/api/...), which
 * Next.js proxies to the backend. Authentication uses an httpOnly cookie, so
 * no token or API key is ever readable by page scripts.
 */
export class ApiError extends Error {
  constructor(public status: number, public code: string, public body?: unknown) {
    super(code);
  }
}

async function handle<T>(res: Response): Promise<T> {
  if (res.ok) {
    const ct = res.headers.get("content-type") || "";
    return (ct.includes("application/json") ? res.json() : (res as unknown)) as Promise<T>;
  }
  let body: unknown = null;
  try {
    body = await res.json();
  } catch {
    /* non-JSON error */
  }
  const detail = (body as { detail?: unknown } | null)?.detail;
  const code = typeof detail === "string" ? detail : `http_${res.status}`;
  if (res.status === 401 && typeof window !== "undefined" && !window.location.pathname.startsWith("/login") && !window.location.pathname.startsWith("/register")) {
    window.location.href = "/login";
  }
  throw new ApiError(res.status, code, detail ?? body);
}

export async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body && !(init.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const res = await fetch(`/api${path}`, { ...init, headers, credentials: "same-origin", cache: "no-store" });
  return handle<T>(res);
}

export const get = <T,>(path: string) => api<T>(path);
export const post = <T,>(path: string, body?: unknown) =>
  api<T>(path, { method: "POST", body: body instanceof FormData ? body : JSON.stringify(body ?? {}) });
export const put = <T,>(path: string, body: unknown) => api<T>(path, { method: "PUT", body: JSON.stringify(body) });
export const del = <T,>(path: string) => api<T>(path, { method: "DELETE" });

/** Upload with progress (fetch has no upload progress events). */
export function uploadWithProgress<T>(form: FormData, onProgress: (pct: number) => void): Promise<T> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", "/api/documents");
    xhr.withCredentials = true;
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(Math.round((e.loaded / e.total) * 100));
    xhr.onload = () => {
      let body: unknown = null;
      try {
        body = JSON.parse(xhr.responseText);
      } catch {
        /* ignore */
      }
      if (xhr.status >= 200 && xhr.status < 300) resolve(body as T);
      else reject(new ApiError(xhr.status, `http_${xhr.status}`, (body as { detail?: unknown } | null)?.detail ?? body));
    };
    xhr.onerror = () => reject(new ApiError(0, "network_error"));
    xhr.send(form);
  });
}
