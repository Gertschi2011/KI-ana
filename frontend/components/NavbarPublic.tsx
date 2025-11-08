'use client';
import Link from 'next/link';

export default function NavbarPublic() {
  return (
    <nav className="bg-white shadow-md p-4 flex justify-between items-center">
      <div className="text-xl font-bold text-purple-700">KI_ana</div>
      <div className="flex space-x-4">
        <Link href="/">Start</Link>
        <Link href="/skills">Fähigkeiten</Link>
        <Link href="/pricing">Preise</Link>
        <Link href="/login">Login</Link>
        <Link href="/register">Registrieren</Link>
      </div>
    </nav>
  );
}
