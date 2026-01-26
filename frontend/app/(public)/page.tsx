import LandingHero from './sections/LandingHero'
import LandingFeatures from './sections/LandingFeatures'
import PricingSection from '../../components/PricingSection'
import FaqAccordion from '../../components/FaqAccordion'
import Link from 'next/link'
import KianaCard from '../../components/ui/KianaCard'
import KianaSectionTitle from '../../components/ui/KianaSectionTitle'

function SectionDivider() {
  return <div className="my-12" style={{ height: 1, background: 'rgba(17,24,39,0.08)' }} />
}

export default function PublicHome() {
  return (
    <div className="grid gap-12">
      <LandingHero />

      <section id="features" className="scroll-mt-24">
        <KianaSectionTitle
          title="Warum KI_ana?"
          subtitle="Weich, lebendig, einladend – und trotzdem kontrolliert und stabil."
        />

        <LandingFeatures />
      </section>

      <SectionDivider />

      <section className="grid gap-4">
        <KianaSectionTitle
          title="Features"
          subtitle="Ein paar Highlights – ohne Tech‑Noise, aber mit Substanz."
        />

        <div className="grid gap-4">
          <div className="grid gap-4 lg:grid-cols-2">
            <KianaCard>
              <div className="text-lg font-semibold">Chat</div>
              <div className="small mt-2">Schnell, sauber, optional mit Explain – nur für Creator/Admin sichtbar.</div>
              <div className="mt-4 grid gap-2">
                <div className="card" style={{ background: 'rgba(147,51,234,0.06)' }}>
                  <div className="text-sm font-semibold">Streaming UI</div>
                  <div className="small mt-1">Antworten kommen live an – ohne Chaos.</div>
                </div>
                <div className="card" style={{ background: 'rgba(37,99,235,0.05)' }}>
                  <div className="text-sm font-semibold">Kontext & Ordnung</div>
                  <div className="small mt-1">Ordner, Threads und ein ruhiges Layout.</div>
                </div>
              </div>
            </KianaCard>

            <KianaCard>
              <div className="text-lg font-semibold">Dashboard</div>
              <div className="small mt-2">Übersicht & Kontrolle: das System fühlt sich wie ein Produkt an, nicht wie ein Playground.</div>
              <div className="mt-4 grid gap-2">
                <div className="card" style={{ background: 'rgba(37,99,235,0.05)' }}>
                  <div className="text-sm font-semibold">Status & Navigation</div>
                  <div className="small mt-1">Alles Wichtige mit einem Klick erreichbar.</div>
                </div>
                <div className="card" style={{ background: 'rgba(147,51,234,0.06)' }}>
                  <div className="text-sm font-semibold">Rollenbasiert</div>
                  <div className="small mt-1">Normal User sieht nur das Nötige. Admin sieht Tools.</div>
                </div>
              </div>
            </KianaCard>
          </div>

          <div className="grid gap-4 lg:grid-cols-2">
            <KianaCard>
              <div className="text-lg font-semibold">Block Viewer</div>
              <div className="small mt-2">Wissensblöcke durchsuchen und verifizieren – nur wenn dein Account die Rechte hat.</div>
              <div className="mt-4 grid gap-2">
                <div className="card" style={{ background: 'rgba(147,51,234,0.06)' }}>
                  <div className="text-sm font-semibold">Verifikation</div>
                  <div className="small mt-1">Signieren/Prüfen für saubere Nachvollziehbarkeit.</div>
                </div>
              </div>
            </KianaCard>

            <KianaCard>
              <div className="text-lg font-semibold">TimeFlow / Monitoring</div>
              <div className="small mt-2">Status und Systemflüsse – damit du immer weißt, was läuft.</div>
              <div className="mt-4 grid gap-2">
                <div className="card" style={{ background: 'rgba(37,99,235,0.05)' }}>
                  <div className="text-sm font-semibold">Monitoring</div>
                  <div className="small mt-1">Metriken und Services im Blick (rollenbasiert).</div>
                </div>
              </div>
            </KianaCard>
          </div>
        </div>
      </section>

      <SectionDivider />

      <PricingSection />

      <SectionDivider />

      <FaqAccordion />

      <footer className="card" style={{ marginTop: 10 }}>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="font-semibold">KI_ana</div>
            <div className="small mt-1">Ein ruhiges KI‑System mit Gedächtnis, Tools und Kontrolle.</div>
          </div>
          <div className="flex items-center gap-4 flex-wrap">
            <Link className="small underline" href="/privacy">Datenschutz</Link>
            <Link className="small underline" href="/impressum">Impressum</Link>
            <Link className="small underline" href="/contact">Kontakt</Link>
          </div>
        </div>
        <div className="small mt-4">© {new Date().getFullYear()} KI_ana</div>
      </footer>
    </div>
  )
}
