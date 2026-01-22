'use client'
export default function PapaPage(){
  return (
    <div className="max-w-5xl mx-auto grid gap-4">
      <div className="card">
        <div className="text-lg font-semibold">👨‍👧 Papa</div>
        <div className="small mt-1">
          Dein persönlicher Bereich für Zusammenfassungen, Erinnerungen und kleine Helfer rund um deine Gespräche.
        </div>
      </div>

      <div className="card">
        <div className="font-semibold">Willkommen</div>
        <div className="small mt-1">
          Wähle links im Chat eine Konversation aus und starte – Papa nutzt deine Inhalte, um Kontext sauber aufzubereiten.
        </div>

        <div className="mt-4 grid gap-3 md:grid-cols-3">
          <div className="kiana-alert">
            <div className="font-medium">Kurz-Zusammenfassung</div>
            <div className="small mt-1">Schneller Überblick über die wichtigsten Punkte.</div>
          </div>
          <div className="kiana-alert">
            <div className="font-medium">Merkliste</div>
            <div className="small mt-1">Wichtige Fakten und Entscheidungen gesammelt.</div>
          </div>
          <div className="kiana-alert">
            <div className="font-medium">Nächste Schritte</div>
            <div className="small mt-1">Konkrete To-dos aus dem Verlauf ableiten.</div>
          </div>
        </div>
      </div>

      <div className="card">
        <div className="font-semibold">Noch keine Inhalte</div>
        <div className="small mt-1">
          Sobald du im Chat Nachrichten hast, erscheinen hier automatisch Zusammenfassungen und hilfreiche Hinweise.
        </div>
      </div>
    </div>
  )
}
