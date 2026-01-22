export default function MonitoringPage(){
  const grafanaUrl = process.env.NEXT_PUBLIC_GRAFANA_URL || '/ops/grafana/'
  const prometheusUrl = process.env.NEXT_PUBLIC_PROMETHEUS_URL || '/ops/prometheus/'

  return (
    <div className="max-w-5xl mx-auto grid gap-4">
      <div className="card">
        <div className="text-lg font-semibold">📈 Monitoring</div>
        <div className="small mt-1">System-Überwachung und Dashboards.</div>
      </div>

      <div className="card">
        <div className="font-semibold mb-2">Dashboards</div>
        <div className="small mb-3">Öffnet in neuem Tab.</div>
        <div className="flex gap-3 flex-wrap">
          <a className="kiana-btn kiana-btn-primary" href={grafanaUrl} target="_blank" rel="noreferrer">Grafana</a>
          <a className="kiana-btn" href={prometheusUrl} target="_blank" rel="noreferrer">Prometheus</a>
        </div>
      </div>
    </div>
  )
}
