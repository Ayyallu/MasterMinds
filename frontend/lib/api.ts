// Shared API client for the admin and student portals.
const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

const TOKEN_KEY = "mm_access_token";
const REFRESH_TOKEN_KEY = "mm_refresh_token";
let refreshInFlight: Promise<boolean> | null = null;

export function getToken(): string | null {
  try {
    return localStorage.getItem(TOKEN_KEY);
  } catch {
    return null;
  }
}

export function setToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(TOKEN_KEY, token);
    else localStorage.removeItem(TOKEN_KEY);
  } catch {
    /* ignore storage errors (private mode, etc.) */
  }
}

export function setRefreshToken(token: string | null): void {
  try {
    if (token) localStorage.setItem(REFRESH_TOKEN_KEY, token);
    else localStorage.removeItem(REFRESH_TOKEN_KEY);
  } catch {
    /* ignore storage errors (private mode, etc.) */
  }
}

export function clearTokens(): void {
  setToken(null);
  setRefreshToken(null);
}

async function refreshSession(): Promise<boolean> {
  if (refreshInFlight) return refreshInFlight;
  refreshInFlight = (async () => {
    let refreshToken: string | null = null;
    try {
      refreshToken = localStorage.getItem(REFRESH_TOKEN_KEY);
    } catch {
      return false;
    }
    if (!refreshToken) return false;
    try {
      const response = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ refresh_token: refreshToken }),
      });
      if (!response.ok) {
        clearTokens();
        return false;
      }
      const data = (await response.json()) as {
        access_token: string;
        refresh_token: string;
      };
      setToken(data.access_token);
      setRefreshToken(data.refresh_token);
      return true;
    } catch {
      return false;
    } finally {
      refreshInFlight = null;
    }
  })();
  return refreshInFlight;
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; auth?: boolean },
  retry: boolean,
): Promise<T> {
  const { method = "GET", body, auth = true } = options;
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (auth) {
    const token = getToken();
    if (token) headers.Authorization = `Bearer ${token}`;
  }
  const resp = await fetch(`${API_BASE_URL}${path}`, {
    method,
    headers,
    body: body === undefined ? undefined : JSON.stringify(body),
  });
  if (resp.status === 401 && auth && retry && await refreshSession()) {
    return request<T>(path, options, false);
  }
  const text = await resp.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!resp.ok) throw new Error(errorMessage(data, resp.status));
  return data as T;
}

/** Turn a FastAPI error body into a readable message (incl. 422 field errors). */
function errorMessage(data: unknown, status: number): string {
  const detail =
    data && typeof data === "object" && "detail" in data
      ? (data as { detail?: unknown }).detail
      : null;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail) && detail.length > 0) {
    return detail
      .map((d: { loc?: unknown[]; msg?: string }) => {
        const field = Array.isArray(d.loc) ? String(d.loc[d.loc.length - 1] ?? "") : "";
        const msg = (d.msg ?? "Invalid value").replace(/^Value error, /, "");
        return field && field !== "body" ? `${field.replaceAll("_", " ")}: ${msg}` : msg;
      })
      .join("; ");
  }
  return `Request failed (${status})`;
}

/** Authenticated fetch for non-JSON bodies (uploads, binary downloads). */
async function rawFetch(path: string, init: RequestInit, retry = true): Promise<Response> {
  const headers = new Headers(init.headers);
  const token = getToken();
  if (token) headers.set("Authorization", `Bearer ${token}`);
  const resp = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  if (resp.status === 401 && retry && (await refreshSession())) {
    return rawFetch(path, init, false);
  }
  return resp;
}

/** Upload a multipart form (e.g. a logo). Returns parsed JSON. */
export async function apiUpload<T = unknown>(path: string, form: FormData, method = "PUT"): Promise<T> {
  const resp = await rawFetch(path, { method, body: form });
  const text = await resp.text();
  let data: unknown = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!resp.ok) throw new Error(errorMessage(data, resp.status));
  return data as T;
}

/** Download an authenticated binary resource (e.g. an image) as a Blob. */
export async function apiBlob(path: string): Promise<Blob> {
  const resp = await rawFetch(path, { method: "GET" });
  if (!resp.ok) throw new Error(`Request failed (${resp.status})`);
  return resp.blob();
}

export async function api<T = unknown>(
  path: string,
  options: { method?: string; body?: unknown; auth?: boolean } = {},
): Promise<T> {
  return request<T>(path, options, true);
}
