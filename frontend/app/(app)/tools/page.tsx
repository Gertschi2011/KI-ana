import Link from 'next/link'

export default function ToolsPage(){
  return (
    <div className="max-w-5xl mx-auto grid gap-4">
      <div className="card">
        <div className="text-lg font-semibold">🧰 Tools</div>
        <div className="small mt-1">Werkzeuge und Viewer im gleichen Dashboard-Look.</div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <Link href="/app/blockviewer" className="card" style={{ display: 'block' }}>
          <div className="font-semibold">🧱 Block Viewer</div>
          <div className="small mt-1">Blöcke und Hashes ansehen.</div>
        </Link>

        <Link href="/app/admin/settings" className="card" style={{ display: 'block' }}>
          <div className="font-semibold">🛠️ Admin / Monitoring</div>
          <div className="small mt-1">Monitoring-Links und Admin-Optionen.</div>
        </Link>
      </div>
    </div>
  )
}
