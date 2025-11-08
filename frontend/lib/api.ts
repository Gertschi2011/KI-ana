export const API_BASE = (process.env.NEXT_PUBLIC_API_BASE?.replace(/\/+$/, '')) || '/api';

async function apiJsonOnce<T>(path: string, opts: RequestInit = {}): Promise<{ ok: boolean; status: number; data?: T; text?: string; }> {
  const res = await fetch(`${API_BASE}${path}`, {
    credentials: 'include',
    headers: { 'Content-Type': 'application/json', ...(opts.headers || {}) },
    ...opts,
  });
  if (!res.ok) {
    const txt = await res.text().catch(() => '');
    return { ok: false, status: res.status, text: txt };
  }
  const data = await res.json().catch(() => (null as any));
  return { ok: true, status: res.status, data };
}

// Try primary route first (e.g., /login), then legacy alias (/auth/login) if 404
async function apiJsonWithFallback<T>(primary: string, legacy: string, opts: RequestInit = {}): Promise<T> {
  const first = await apiJsonOnce<T>(primary, opts);
  if (first.ok) return first.data as T;
  if (first.status !== 404) {
    throw new Error(`API ${primary} failed: ${first.status} ${first.text || ''}`.trim());
  }
  const second = await apiJsonOnce<T>(legacy, opts);
  if (second.ok) return second.data as T;
  throw new Error(`API ${legacy} failed: ${second.status} ${second.text || ''}`.trim());
}

export async function apiJson<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const out = await apiJsonOnce<T>(path, opts);
  if (out.ok) return out.data as T;
  throw new Error(`API ${path} failed: ${out.status} ${out.text || ''}`.trim());
}

export async function getMe() {
  try {
    return await apiJsonWithFallback<{ auth: boolean; user?: { username?: string; email?: string } }>(`/me`, `/auth/me`);
  } catch {
    return { auth: false as const };
  }
}

export async function login(payload: { username: string; password: string; remember?: boolean }) {
  // Try modern /api/login; fall back to /api/auth/login if needed
  return apiJsonWithFallback(`/login`, `/auth/login`, { method: 'POST', body: JSON.stringify(payload) });
}

export async function logout() {
  try { await apiJsonWithFallback(`/logout`, `/auth/logout`, { method: 'POST' }); } catch {}
}

export async function register(payload: { username: string; email: string; password: string }) {
  return apiJsonWithFallback(`/register`, `/auth/register`, { method: 'POST', body: JSON.stringify(payload) });
}

// Lightweight wrapper to match older imports like `import { API } from '../../lib/api'`
export const API = {
  async get<T = any>(path: string) {
    return apiJson<T>(path);
  },
  async post<T = any>(path: string, body: any) {
    return apiJson<T>(path, { method: 'POST', body: JSON.stringify(body) });
  },
};
