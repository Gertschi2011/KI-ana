import Link from 'next/link'

type Plan = {
  name: string
  price: string
  highlight?: boolean
  badge?: string
  bullets: string[]
  ctaLabel: string
  ctaHref: string
}

export default function PricingSection() {
  const plans: Plan[] = [
    {
      name: 'Free',
      price: 'Gratis',
      bullets: [
        'Chat mit KI_ana (Streaming)',
        'Ordner & Konversationen',
        'Einstellungen & Profil',
        'Basis-Rollen (User)',
        'Mobil nutzbar',
      ],
      ctaLabel: 'Jetzt starten',
      ctaHref: '/register',
    },
    {
      name: 'Creator',
      price: 'Für Power-User',
      highlight: true,
      badge: 'Beliebt',
      bullets: [
        'Creator/Admin Funktionen',
        'Tools & Monitoring Zugriff',
        'Block Viewer + Verifizieren',
        'Audit/Logs & Admin-Übersichten',
        'Explain optional (kontrolliert)',
        'Schneller Support',
      ],
      ctaLabel: 'Upgrade / Registrieren',
      ctaHref: '/register',
    },
    {
      name: 'Team / Pro',
      price: 'Coming soon',
      badge: 'Bald verfügbar',
      bullets: [
        'Team-Rollen & Policies',
        'Mehr Rechte-Profile & Caps',
        'SLA / Enterprise Optionen',
        'Onboarding & Migration',
        'Custom Integrationen',
      ],
      ctaLabel: 'Kontakt',
      ctaHref: '/contact',
    },
  ]

  return (
    <section id="pricing" className="scroll-mt-24">
      <div className="text-center mb-8">
        <div className="text-3xl font-bold">Pakete</div>
        <div className="small mt-2">Ein klarer Einstieg – und ein Upgrade-Pfad, wenn du mehr Kontrolle brauchst.</div>
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

            <div className="mt-2" style={{ fontSize: 28, fontWeight: 800 }}>
              {p.price}
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
        Hinweis: Preise/Details können sich ändern. Für Teams: einfach Kontakt aufnehmen.
      </div>
    </section>
  )
}
