export const API = {
  base: process.env.NEXT_PUBLIC_API_BASE || 'http://localhost:8000',
  async get<T>(path: string): Promise<T> {
    const r = await fetch(`${this.base}${path}`, { cache: 'no-store' });
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  },
  async post<T>(path: string, body: any): Promise<T> {
    const r = await fetch(`${this.base}${path}`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body)});
    if (!r.ok) throw new Error(`${r.status}`);
    return r.json();
  }
};
