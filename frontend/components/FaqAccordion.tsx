'use client'

import { useMemo, useState } from 'react'

type Faq = { q: string; a: string }

export default function FaqAccordion() {
  const faqs = useMemo<Faq[]>(
    () => [
      {
        q: 'Was ist KI_ana?',
        a: 'KI_ana ist ein persönliches KI‑System, das Chat, Tools und Kontrolle in einem Dashboard bündelt – mit Rollen, Protokollen und (optional) Wissensblöcken.',
      },
      {
        q: 'Muss ich mich registrieren?',
        a: 'Für die App‑Funktionen unter /app brauchst du ein Konto. Die Landingpage ist frei zugänglich.',
      },
      {
        q: 'Was passiert mit meinen Daten?',
        a: 'KI_ana ist datenschutz‑fokussiert. Was gespeichert wird, ist transparent; Rollen und Berechtigungen sorgen dafür, dass nicht jeder alles sieht.',
      },
      {
        q: 'Was bedeutet Explain?',
        a: 'Explain ist eine optionale, kontrollierte Zusatzansicht, die bei Bedarf erklärt, wie eine Antwort zustande kam. Für normale Nutzer bleibt es einfach und ruhig.',
      },
      {
        q: 'Welche Rollen gibt es?',
        a: 'Typisch sind User, Creator und Admin. Rollen steuern Menüs, Tools und Zugriffsrechte – so bleibt die Oberfläche für normale Nutzer schlank.',
      },
      {
        q: 'Kann ich später upgraden?',
        a: 'Ja. Du kannst jederzeit von Free auf Creator/Pro wechseln (je nach Verfügbarkeit).',
      },
      {
        q: 'Ist das mobil nutzbar?',
        a: 'Ja. Das UI ist mobile‑first und passt sich responsiv an.',
      },
      {
        q: 'Wie sicher ist das?',
        a: 'Sessions, Rollen/Caps, Audit/Logs und klare Trennung zwischen Public und App‑Bereich sind Kernprinzipien. Details hängen vom Deployment ab.',
      },
      {
        q: 'Gibt es eine Demo?',
        a: 'Ohne Login zeigen wir dir Features & Screens als Vorschau. Mit Login kannst du direkt in /app/chat starten.',
      },
    ],
    [],
  )

  const [open, setOpen] = useState<number | null>(0)

  return (
    <section id="faq" className="scroll-mt-24">
      <div className="text-center mb-8">
        <div className="text-3xl font-bold">FAQ</div>
        <div className="small mt-2">Kurze Antworten auf die wichtigsten Fragen.</div>
      </div>

      <div className="grid gap-3">
        {faqs.map((f, idx) => {
          const isOpen = open === idx
          return (
            <div key={f.q} className="card" style={{ padding: 0, overflow: 'hidden' }}>
              <button
                type="button"
                onClick={() => setOpen(isOpen ? null : idx)}
                className="w-full text-left"
                style={{
                  padding: '18px 20px',
                  display: 'flex',
                  alignItems: 'center',
                  justifyContent: 'space-between',
                  gap: 12,
                }}
              >
                <div style={{ fontWeight: 700 }}>{f.q}</div>
                <div
                  aria-hidden="true"
                  style={{
                    width: 32,
                    height: 32,
                    borderRadius: 999,
                    background: isOpen ? 'rgba(147,51,234,0.10)' : 'rgba(37,99,235,0.08)',
                    border: '1px solid rgba(17,24,39,0.08)',
                    display: 'flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    fontWeight: 900,
                    color: 'rgba(17,24,39,0.80)',
                  }}
                >
                  {isOpen ? '–' : '+'}
                </div>
              </button>

              {isOpen ? (
                <div style={{ padding: '0 20px 18px 20px' }}>
                  <div className="small" style={{ fontSize: 15, lineHeight: 1.65 }}>
                    {f.a}
                  </div>
                </div>
              ) : null}
            </div>
          )
        })}
      </div>
    </section>
  )
}
