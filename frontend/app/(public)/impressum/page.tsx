export default function ImpressumPage() {
  return (
    <div className="grid gap-4">
      <div className="card">
        <div className="text-2xl font-bold">Impressum</div>
        <div className="small mt-2">
          Platzhalter – bitte mit den rechtlich erforderlichen Angaben (Betreiber, Adresse, Kontakt, UID etc.) ergänzen.
        </div>
      </div>

      <div className="card">
        <div className="font-semibold">Kontakt</div>
        <div className="small mt-2">Siehe <a className="underline" href="/contact">Kontakt</a>.</div>
      </div>
    </div>
  )
}
