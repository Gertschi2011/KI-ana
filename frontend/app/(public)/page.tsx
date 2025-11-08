export default function PublicHome() {
  return (
    <section className="max-w-5xl mx-auto">
      <div className="flex items-center gap-3 mb-6">
        <div className="text-3xl">💜</div>
        <h1 className="text-3xl font-bold">Willkommen bei KI_ana 2.0</h1>
      </div>
      <p className="text-lg text-gray-700 mb-6">
        Deine persönliche KI – sicher, modern und immer für dich da. Starte eine Unterhaltung, entdecke Fähigkeiten oder passe deine Einstellungen an.
      </p>
      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <a className="card" href="/login"><span>💬 Chat</span><small>Bitte zuerst anmelden</small></a>
        <a className="card" href="/skills"><span>✨ Fähigkeiten</span><small>Was KI_ana kann</small></a>
        <a className="card" href="/pricing"><span>💰 Preise</span><small>Pläne & Optionen</small></a>
        <a className="card" href="/login"><span>🔐 Login</span><small>Anmelden</small></a>
        <a className="card" href="/register"><span>🆕 Registrieren</span><small>Konto erstellen</small></a>
      </div>
    </section>
  );
}
