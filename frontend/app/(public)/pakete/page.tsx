import Link from 'next/link'
import PricingSection from '../../../components/PricingSection'
import KianaCard from '../../../components/ui/KianaCard'
import KianaSectionTitle from '../../../components/ui/KianaSectionTitle'

export default function PaketePage() {
  return (
    <div className="grid gap-10">
      <KianaSectionTitle
        title="Pakete"
        subtitle="Wähle den Einstieg, der sich gut anfühlt. Du kannst später jederzeit wachsen."
      />

      <PricingSection />

      <KianaCard>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="text-lg font-semibold">Bereit für ein erstes Gespräch?</div>
            <div className="small mt-1">Ein erstes Gespräch reicht oft, um das Gefühl zu bekommen.</div>
          </div>
          <Link href="/register" className="kiana-btn2 kiana-btn2-primary">Kostenlos starten</Link>
        </div>
        <div className="small mt-3">
          Oder zurück zur <Link className="underline" href="/">Startseite</Link>.
        </div>
      </KianaCard>
    </div>
  )
}
