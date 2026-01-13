export default function AdminSettingsPage(){
  const grafanaUrl = process.env.NEXT_PUBLIC_GRAFANA_URL || '/ops/grafana/'
  const prometheusUrl = process.env.NEXT_PUBLIC_PROMETHEUS_URL || '/ops/prometheus/'

  return (
    <div className="p-4">
      <h1 className="text-2xl font-bold mb-4">Admin-Einstellungen</h1>

      <div className="card mb-4">
        <div className="font-semibold mb-2">Monitoring</div>
        <div className="text-sm text-gray-300 mb-3">
          Links öffnen in neuem Tab. Falls du hier 404 siehst, fehlt noch ein Reverse-Proxy auf dem Server
          (z.B. /ops/grafana/ → Grafana).
        </div>
        <div className="flex gap-3 flex-wrap">
          <a className="btn-dark" href={grafanaUrl} target="_blank" rel="noreferrer">Grafana (Quality)</a>
          <a className="btn-dark" href={prometheusUrl} target="_blank" rel="noreferrer">Prometheus</a>
        </div>
      </div>

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
