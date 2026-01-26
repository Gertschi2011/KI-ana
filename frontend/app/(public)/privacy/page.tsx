export default function PrivacyPage() {
  return (
    <div className="grid gap-4">
      <div className="card">
        <div className="text-2xl font-bold">Datenschutz</div>
        <div className="small mt-2">
          Diese Seite ist eine kurze, menschliche Übersicht. Für verbindliche Details wird die formale Datenschutzerklärung noch ergänzt.
        </div>
      </div>

      <div className="card">
        <div className="font-semibold">Kurzfassung</div>
        <ul className="mt-3 grid gap-2">
          <li className="small">• Deine Inhalte gehören dir. KI_ana nutzt sie, um dir zu antworten – nicht, um dich zu nerven.</li>
          <li className="small">• Dein Bereich ist geschützt: Ohne Login kommt niemand an deine Gespräche.</li>
          <li className="small">• Wenn KI_ana sich etwas merken soll, passiert das nicht heimlich – sondern gemeinsam und nachvollziehbar.</li>
        </ul>
        <div className="small mt-3" style={{ opacity: 0.8 }}>
          Hinweis: Diese Seite ist eine Übersicht und ersetzt keine rechtliche Beratung.
        </div>
      </div>
    </div>
  )
}
