export default function AdminSettingsPage(){
  const grafanaUrl = process.env.NEXT_PUBLIC_GRAFANA_URL || '/ops/grafana/'
  const prometheusUrl = process.env.NEXT_PUBLIC_PROMETHEUS_URL || '/ops/prometheus/'

  return (
    <div className="max-w-5xl mx-auto grid gap-4">
      <div className="card">
        <div className="text-lg font-semibold">Admin</div>
        <div className="small mt-1">Monitoring-Links und Systemoptionen im gleichen Look wie der Rest der App.</div>
      </div>

      <div className="card">
        <div className="font-semibold mb-2">Monitoring</div>
        <div className="small mb-3">
          Öffnet in neuem Tab. Wenn du 404 siehst, fehlt ggf. ein Reverse-Proxy-Pfad auf dem Server.
        </div>
        <div className="flex gap-3 flex-wrap">
          <a className="kiana-btn kiana-btn-primary" href={grafanaUrl} target="_blank" rel="noreferrer">Grafana</a>
          <a className="kiana-btn" href={prometheusUrl} target="_blank" rel="noreferrer">Prometheus</a>
        </div>
      </div>

      <div className="card">
        <div className="font-semibold mb-2">Systemeinstellungen</div>
        <div className="kiana-alert">
          <div className="font-medium">Keine Optionen verfügbar</div>
          <div className="small mt-1">Aktuell gibt es in der Weboberfläche keine konfigurierbaren Admin-Optionen.</div>
        </div>
      </div>
    </div>
  )
}
