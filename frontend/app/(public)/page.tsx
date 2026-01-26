import LandingHero from './sections/LandingHero'
import LandingFeatures from './sections/LandingFeatures'
import PricingSection from '../../components/PricingSection'
import FaqAccordion from '../../components/FaqAccordion'
import Link from 'next/link'
import KianaCard from '../../components/ui/KianaCard'
import KianaButton from '../../components/ui/KianaButton'
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
          subtitle="Für Menschen, die nicht „besser prompten“ wollen – sondern verstanden werden."
        />

        <LandingFeatures />
      </section>

      <SectionDivider />

      <section id="wie" className="grid gap-4 scroll-mt-24">
        <KianaSectionTitle
          title="So funktioniert KI_ana"
          subtitle="Drei Schritte – ganz ohne Technik‑Gerede."
        />

        <KianaCard>
          <div className="grid gap-4" style={{ maxWidth: 820, margin: '0 auto' }}>
            <div className="grid gap-3 md:grid-cols-3">
              <KianaCard hover style={{ background: 'rgba(37,99,235,0.06)', borderRadius: 18 }}>
                <div className="text-sm" style={{ fontWeight: 800, opacity: 0.85 }}>1) Du redest</div>
                <div className="mt-1">Ganz normal. Ohne „Prompt‑Magie". So wie du bist.</div>
              </KianaCard>
              <KianaCard hover style={{ background: 'rgba(147,51,234,0.07)', borderRadius: 18 }}>
                <div className="text-sm" style={{ fontWeight: 800, opacity: 0.85 }}>2) KI_ana fragt nach</div>
                <div className="mt-1">Wenn etwas wichtig wirkt, fragt sie kurz nach – statt zu raten.</div>
              </KianaCard>
              <KianaCard hover style={{ background: 'rgba(37,99,235,0.06)', borderRadius: 18 }}>
                <div className="text-sm" style={{ fontWeight: 800, opacity: 0.85 }}>3) KI_ana merkt es sich</div>
                <div className="mt-1">Damit sie beim nächsten Mal schon weiß, was du meinst.</div>
              </KianaCard>
            </div>

            <div className="small" style={{ textAlign: 'center', marginTop: 2, opacity: 0.85 }}>
              Kurz gesagt: KI_ana lernt nicht heimlich – sie lernt mit dir.
            </div>

            <div className="mt-2 flex items-center justify-center gap-3 flex-wrap">
              <Link href="/register">
                <KianaButton variant="primary">Im Chat starten</KianaButton>
              </Link>
              <Link href="/pakete">
                <KianaButton variant="secondary">Pakete anschauen</KianaButton>
              </Link>
            </div>
          </div>
        </KianaCard>
      </section>

      <SectionDivider />

      <PricingSection />

      <section className="grid gap-4">
        <KianaCard>
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="text-lg font-semibold">Bereit für ein erstes Gespräch?</div>
              <div className="small mt-1">Nimm dir 2 Minuten. Danach weißt du, ob KI_ana zu dir passt.</div>
            </div>
            <Link href="/register">
              <KianaButton variant="primary">KI_ana kennenlernen</KianaButton>
            </Link>
          </div>
        </KianaCard>
      </section>

      <SectionDivider />

      <FaqAccordion />

      <footer className="card" style={{ marginTop: 10 }}>
        <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
          <div>
            <div className="font-semibold">KI_ana</div>
            <div className="small mt-1">Eine ruhige KI mit Gedächtnis – und einem weichen Gefühl.</div>
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
