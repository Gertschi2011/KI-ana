'use client'
import KianaCard from '../../../components/ui/KianaCard'
import KianaButton from '../../../components/ui/KianaButton'
export default function PapaPage(){
  return (
    <div className="max-w-5xl mx-auto grid gap-4">
      <KianaCard>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="text-lg font-semibold">Papa</div>
            <div className="small mt-1">Dein persönlicher Bereich für Zusammenfassungen, Erinnerungen und ruhige Helfer.</div>
          </div>
          <a href="/app/chat">
            <KianaButton variant="primary">Zum Chat</KianaButton>
          </a>
        </div>

        <div className="kiana-inset mt-5">
          <div className="font-semibold">Willkommen</div>
          <div className="small mt-1">
            Wähle im Chat links eine Konversation aus – Papa nimmt den Faden sanft auf und hilft dir, den Überblick zu behalten.
          </div>

          <div className="mt-4 grid gap-3 md:grid-cols-3">
            <div className="rounded-2xl p-4" style={{ background: 'rgba(147,51,234,0.06)', border: '1px solid rgba(17,24,39,0.08)' }}>
              <div className="font-medium">Kurz-Zusammenfassung</div>
              <div className="small mt-1">Ein weicher Überblick über das Wesentliche.</div>
            </div>
            <div className="rounded-2xl p-4" style={{ background: 'rgba(37,99,235,0.05)', border: '1px solid rgba(17,24,39,0.08)' }}>
              <div className="font-medium">Merkliste</div>
              <div className="small mt-1">Wichtige Fakten und Entscheidungen gesammelt.</div>
            </div>
            <div className="rounded-2xl p-4" style={{ background: 'rgba(110,195,244,0.08)', border: '1px solid rgba(17,24,39,0.08)' }}>
              <div className="font-medium">Nächste Schritte</div>
              <div className="small mt-1">Konkrete Ideen, die dir sanft weiterhelfen.</div>
            </div>
          </div>
        </div>

        <div className="kiana-inset mt-4">
          <div className="font-semibold">Inhalte entstehen automatisch</div>
          <div className="small mt-1">
            Sobald du ein paar Nachrichten im Chat hast, tauchen hier Zusammenfassungen und Hinweise auf.
          </div>
        </div>
      </KianaCard>
    </div>
  )
}
