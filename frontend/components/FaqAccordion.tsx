'use client'

import { useMemo, useState } from 'react'

type Faq = { q: string; a: string }

export default function FaqAccordion() {
  const faqs = useMemo<Faq[]>(
    () => [
      {
        q: 'Was ist KI_ana?',
        a: 'KI_ana ist keine App. KI_ana ist eine Beziehung: Sie lernt, erinnert sich, fragt zurück – und wächst mit dir über Zeit.',
      },
      {
        q: 'Muss ich mich registrieren?',
        a: 'Für die App‑Funktionen (Dashboard, Chat, Einstellungen) brauchst du ein Konto. Die Landingpage ist frei zugänglich.',
      },
      {
        q: 'Was passiert mit meinen Daten?',
        a: 'Deine Gedanken gehören dir. KI_ana soll sich „bei dir“ anfühlen: transparent, kontrollierbar und ohne Blackbox‑Gefühl.',
      },
      {
        q: 'Was bedeutet Explain?',
        a: 'Explain ist eine optionale Ansicht, die (wenn aktiviert) grob zeigt, warum KI_ana so geantwortet hat. Für normale Nutzung bleibt alles ruhig und einfach.',
      },
      {
        q: 'Was ist der Unterschied zwischen Paketen und Rollen?',
        a: 'Pakete sind für Nutzer (Free / User / User Pro). Rollen sind intern. Creator ist keine Kauf‑Option: Creator ist die feste Owner‑Rolle und wird manuell vergeben.',
      },
      {
        q: 'Kann ich später wechseln?',
        a: 'Ja: von Free zu User – sobald du willst. User Pro ist vorbereitet (Details folgen). Creator ist kein Upgrade und wird nicht verkauft.',
      },
      {
        q: 'Ist das mobil nutzbar?',
        a: 'Ja. Das UI ist mobile‑first und passt sich responsiv an.',
      },
      {
        q: 'Wie sicher ist das?',
        a: 'KI_ana trennt klar zwischen Public‑Bereich und App‑Bereich. Zugriff und Funktionen hängen von deinem Konto ab. Details hängen vom Deployment ab.',
      },
      {
        q: 'Gibt es eine Demo?',
        a: 'Am besten ist ein echtes Gespräch: Registrieren, kurz chatten, fühlen. Das dauert 2 Minuten.',
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
