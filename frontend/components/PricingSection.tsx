import Link from 'next/link'

type Plan = {
  name: string
  highlight?: boolean
  badge?: string
  goal: string
  description: string
  bullets: string[]
  ctaLabel: string
  ctaHref: string
}

export default function PricingSection() {
  const plans: Plan[] = [
    {
      name: 'Free',
      goal: 'Kennenlernen, Vertrauen aufbauen',
      description: 'Der Einstieg in KI_ana. Reden, ausprobieren, fühlen.',
      bullets: [
        'Chat mit KI_ana',
        'Kurzzeit‑Kontext (pro Sitzung)',
        'Keine Langzeit‑Erinnerung',
        'Keine Lernfreigaben',
      ],
      ctaLabel: 'Kostenlos starten',
      ctaHref: '/register',
    },
    {
      name: 'User',
      highlight: true,
      badge: 'Alltag',
      goal: 'Alltag, echte Beziehung',
      description: 'KI_ana merkt sich, was dir wichtig ist und entwickelt ein Verständnis für dich.',
      bullets: [
        'Alles aus Free',
        'Persönliches Langzeitgedächtnis',
        'Rückfragen: „Soll ich mir das merken?“',
        'Einfaches Dashboard',
        'Persönliche Einstellungen',
      ],
      ctaLabel: 'KI_ana persönlich machen',
      ctaHref: '/register',
    },
    {
      name: 'User Pro',
      badge: 'Vorbereitet',
      goal: 'Power‑User, Denkpartner, Tiefe',
      description: 'Für Menschen, die mehr wollen als Antworten. (Details noch offen – aber vorbereitet.)',
      bullets: [
        'Größeres Langzeitgedächtnis (optional)',
        'Themen‑Gedächtnisse (z. B. Projekte, Interessen)',
        'Reflexionsfragen von KI_ana',
        'Export / Verlauf / Analyse',
        'Priorisierte Weiterentwicklung',
        'Kein Zugriff auf Papa Tools / Systemlogik',
      ],
      ctaLabel: 'Interesse an User Pro',
      ctaHref: '/contact',
    },
  ]

  return (
    <section id="pakete" className="scroll-mt-24">
      <div id="pricing" style={{ position: 'relative', top: -96 }} aria-hidden />
      <div className="text-center mb-8">
        <div className="text-3xl font-bold">Pakete</div>
        <div className="small mt-2">Keine Preise. Keine Upsells. Nur ein klarer Einstieg – und ein Weg in die Beziehung.</div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {plans.map((p) => (
          <div
            key={p.name}
            className="card"
            style={
              p.highlight
                ? {
                    border: '1px solid rgba(147,51,234,0.28)',
                    boxShadow: '0 14px 38px rgba(37,99,235,0.10)',
                  }
                : undefined
            }
          >
            <div className="flex items-center justify-between gap-2">
              <div className="text-lg font-semibold">{p.name}</div>
              {p.badge ? (
                <span
                  className={`text-xs px-2 py-1 rounded-full ${p.highlight ? 'kiana-badge-pulse' : ''}`}
                  style={{
                    background: p.highlight ? 'rgba(147,51,234,0.10)' : 'rgba(37,99,235,0.08)',
                    color: 'rgba(17,24,39,0.82)',
                    border: '1px solid rgba(17,24,39,0.08)',
                  }}
                >
                  {p.badge}
                </span>
              ) : null}
            </div>

            <div className="mt-2 small" style={{ color: 'rgba(17,24,39,0.75)' }}>
              <span style={{ fontWeight: 800 }}>Ziel:</span> {p.goal}
            </div>
            <div className="mt-2" style={{ fontSize: 16, lineHeight: 1.6, color: 'rgba(17,24,39,0.80)' }}>
              {p.description}
            </div>

            <ul className="mt-4 grid gap-2">
              {p.bullets.map((b) => (
                <li key={b} className="small" style={{ display: 'flex', gap: 10 }}>
                  <span aria-hidden="true" style={{ color: 'rgba(37,99,235,0.9)' }}>
                    ✓
                  </span>
                  <span>{b}</span>
                </li>
              ))}
            </ul>

            <div className="mt-6">
              <Link className="kiana-btn2 kiana-btn2-primary w-full" href={p.ctaHref}>
                {p.ctaLabel}
              </Link>
            </div>
          </div>
        ))}
      </div>

      <div className="small text-center mt-6">
        Hinweis: Creator‑Funktionen sind keine „Upgrades“. Creator ist eine feste Sonderrolle (Owner) und wird manuell vergeben.
      </div>
    </section>
  )
}
