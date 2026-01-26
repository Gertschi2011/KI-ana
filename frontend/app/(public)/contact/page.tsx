import Link from 'next/link'

export default function ContactPage() {
  return (
    <div className="grid gap-4">
      <div className="card">
        <div className="text-2xl font-bold">Kontakt</div>
        <div className="small mt-2">Du willst Team/Pro oder eine Einladung? Schreib uns.</div>
      </div>

      <div className="card">
        <div className="font-semibold">Optionen</div>
        <div className="small mt-2">• Per E‑Mail/Support (je nach Deployment)</div>
        <div className="small">• Oder direkt registrieren und später upgraden</div>
        <div className="mt-4 flex gap-3 flex-wrap">
          <Link className="kiana-btn kiana-btn-primary" href="/register">Registrieren</Link>
          <Link className="kiana-btn" href="/login">Login</Link>
        </div>
      </div>
    </div>
  )
}
