export default function AdminSettingsPage(){
  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Admin-Einstellungen</h1>
      <div className="card">
        <form className="grid gap-3 max-w-xl">
          <label className="block">
            <div className="mb-1">Systemmodus</div>
            <select className="input">
              <option>Normal</option>
              <option>Wartung</option>
            </select>
          </label>
          <label className="block">
            <div className="mb-1">Web-Recherche erlauben</div>
            <select className="input">
              <option>Standard</option>
              <option>Erzwingen</option>
              <option>Deaktivieren</option>
            </select>
          </label>
          <button className="btn-dark" type="button">Speichern (Platzhalter)</button>
        </form>
      </div>
    </div>
  )
}
