import Link from 'next/link'
import KianaCard from './ui/KianaCard'
import KianaButton from './ui/KianaButton'

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
      goal: 'Ankommen, ausprobieren, Gefühl bekommen',
      description: 'Für den ersten Kontakt: leicht, freundlich, ohne Druck. Einfach reden und schauen, ob es passt.',
      bullets: [
        'Einfach chatten – ohne „Prompt‑Magie“',
        'KI_ana bleibt im Moment (merkt sich noch nichts dauerhaft)',
        'Du bekommst ein Gefühl für Ton & Tempo',
        'Jederzeit aufhören – kein Verkaufsdruck',
      ],
      ctaLabel: 'Kostenlos starten',
      ctaHref: '/register',
    },
    {
      name: 'User',
      highlight: true,
      badge: 'Alltag',
      goal: 'Alltag, echte Beziehung',
      description: 'Für Menschen, die bleiben: KI_ana darf sich Dinge merken – und wird über Zeit spürbar „deine“ KI.',
      bullets: [
        'Alles aus Free',
        'KI_ana erkennt dich wieder',
        'Sie fragt sanft: „Soll ich mir das merken?“',
        'Ein ruhiges Dashboard, das dich abholt',
        'Stil & Stimme so, wie es sich gut anfühlt',
      ],
      ctaLabel: 'Als User starten',
      ctaHref: '/register',
    },
    {
      name: 'User Pro',
      badge: 'Vorbereitet',
      goal: 'Tiefe, Fokus, Denkpartner',
      description: 'Für Menschen, die regelmäßig mit KI_ana arbeiten und mehr Raum für Themen & Struktur wollen.',
      bullets: [
        'Mehr Platz für deine Themen (z. B. Projekte, Interessen)',
        'Bessere Übersicht über längere Verläufe',
        'Reflexionsfragen, wenn es dich weiterbringt',
        'Mitgestalten: Feedback fließt schneller ein',
        'Papa Tools bleiben Gerald vorbehalten',
      ],
      ctaLabel: 'Interesse vormerken',
      ctaHref: '/contact',
    },
  ]

  return (
    <section id="pakete" className="scroll-mt-24">
      <div id="pricing" style={{ position: 'relative', top: -96 }} aria-hidden />
      <div className="text-center mb-8">
        <div className="text-3xl font-bold">Pakete</div>
        <div className="small mt-2">Keine Preise hier. Kein Verkaufsdruck. Nur ein Einstieg, der sich gut anfühlt.</div>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        {plans.map((p) => (
          <KianaCard
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
                  className="text-xs px-2 py-1 rounded-full"
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
              <Link href={p.ctaHref} className="w-full">
                <KianaButton variant="primary" className="w-full">{p.ctaLabel}</KianaButton>
              </Link>
            </div>
          </KianaCard>
        ))}
      </div>

      <div className="small text-center mt-6">
        Hinweis: Gerald (Creator) ist kein Paket. Papa Tools sind nicht kaufbar.
      </div>
    </section>
  )
}
