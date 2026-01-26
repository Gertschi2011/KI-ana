export default function PrivacyPage() {
  return (
    <div className="grid gap-4">
      <div className="card">
        <div className="text-2xl font-bold">Datenschutz</div>
        <div className="small mt-2">
          Diese Seite ist eine kurze Übersicht. Für verbindliche Details bitte die produktive Datenschutzerklärung ergänzen.
        </div>
      </div>

      <div className="card">
        <div className="font-semibold">Kurzfassung</div>
        <ul className="mt-3 grid gap-2">
          <li className="small">• Public Landingpage ist ohne Login nutzbar.</li>
          <li className="small">• /app/* ist geschützt und erfordert Authentifizierung.</li>
          <li className="small">• Rollen und Berechtigungen begrenzen Zugriffe innerhalb der App.</li>
        </ul>
      </div>
    </div>
  )
}
