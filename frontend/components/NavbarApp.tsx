'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { getMe, logout as apiLogout } from '../lib/api';

export default function NavbarApp() {
  const [username, setUsername] = useState<string | null>(null);
  const [isAuthed, setIsAuthed] = useState<boolean | null>(null);
  const grafanaUrl = process.env.NEXT_PUBLIC_GRAFANA_URL || '/ops/grafana/';

  useEffect(() => {
    let mounted = true;
    (async () => {
      try {
        const me: any = await getMe();
        if (!mounted) return;
        if (me?.auth) {
          setIsAuthed(true);
          const u = me?.user?.username || me?.user?.email || null;
          setUsername(u);
          try { if (u) localStorage.setItem('kiana_username', String(u)); } catch {}
        } else {
          setIsAuthed(false);
          const u = typeof window !== 'undefined' ? localStorage.getItem('kiana_username') : null;
          setUsername(u);
        }
      } catch {
        if (!mounted) return;
        setIsAuthed(false);
      }
    })();
    return () => { mounted = false; };
  }, []);

  async function logout() {
    try { await apiLogout(); } catch {}
    try { localStorage.removeItem('kiana_username'); } catch {}
    setIsAuthed(false);
    setUsername(null);
    window.location.href = '/login';
  }

  return (
    <nav className="bg-gray-900 text-white p-4 flex justify-between items-center">
      <div className="text-xl font-bold">KI_ana</div>
      <div className="flex space-x-4">
        <Link href="/app/chat">Chat</Link>
        <a href="/dashboard">Tools</a>
        <Link href="/app/papa">Papa</Link>
        <a href={grafanaUrl} target="_blank" rel="noreferrer">Monitoring</a>
        <Link href="/app/settings">Einstellungen</Link>
        <Link href="/app/admin/users">Admin</Link>
      </div>
      <div className="flex items-center space-x-2">
        {isAuthed ? (
          <>
            <span>{username || 'User'}</span>
            <button onClick={logout} className="bg-red-600 px-2 py-1 rounded">
              Logout
            </button>
          </>
        ) : (
          <Link className="bg-gray-700 px-2 py-1 rounded" href="/login">Login</Link>
        )}
      </div>
    </nav>
  );
}
