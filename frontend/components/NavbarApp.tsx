'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';

export default function NavbarApp() {
  const [username, setUsername] = useState<string | null>(null);

  useEffect(() => {
    const u = typeof window !== 'undefined' ? localStorage.getItem('kiana_username') : null;
    if (u) setUsername(u);
  }, []);

  function logout() {
    try { localStorage.removeItem('kiana_username'); localStorage.clear(); } catch {}
    window.location.href = '/';
  }

  return (
    <nav className="bg-gray-900 text-white p-4 flex justify-between items-center">
      <div className="text-xl font-bold">KI_ana</div>
      <div className="flex space-x-4">
        <Link href="/chat">Chat</Link>
        <Link href="/papa">Papa</Link>
        <Link href="/settings">Einstellungen</Link>
        <Link href="/admin/users">Admin</Link>
      </div>
      <div className="flex items-center space-x-2">
        <span>{username || 'Gast'}</span>
        <button onClick={logout} className="bg-red-600 px-2 py-1 rounded">
          Logout
        </button>
      </div>
    </nav>
  );
}
