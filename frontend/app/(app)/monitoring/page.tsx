'use client'

import { useEffect, useState } from 'react'
import KianaCard from '../../../components/ui/KianaCard'
import KianaButton from '../../../components/ui/KianaButton'

export default function MonitoringPage(){
  const [access, setAccess] = useState<'loading' | 'denied' | 'allowed'>('loading')
  const grafanaUrl = process.env.NEXT_PUBLIC_GRAFANA_URL || '/ops/grafana/'
  const prometheusUrl = process.env.NEXT_PUBLIC_PROMETHEUS_URL || '/ops/prometheus/'

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const r = await fetch('/api/me', { credentials: 'include' })
        const me = await r.json().catch(() => ({} as any))
        const u: any = me?.auth ? me?.user : null
        const role = String(u?.role ?? '').toLowerCase()
        const roles = Array.isArray(u?.roles) ? u.roles.map((x: any) => String(x).toLowerCase()) : []
        const isAdmin = !!u?.is_admin || roles.includes('admin') || role === 'admin'
        const isCreator = !!u?.is_creator || roles.includes('creator') || role === 'creator'
        const allowed = Boolean(isAdmin || isCreator)
        if (!mounted) return
        setAccess(allowed ? 'allowed' : 'denied')
      } catch {
        if (!mounted) return
        setAccess('denied')
      }
    })()
    return () => { mounted = false }
  }, [])

  if (access === 'loading') {
    return (
      <div className="max-w-5xl mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">Monitoring</div>
          <div className="small mt-1">Prüfe Zugriff…</div>
        </KianaCard>
      </div>
    )
  }

  if (access === 'denied') {
    return (
      <div className="max-w-5xl mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">Monitoring</div>
          <div className="small mt-1">Kein Zugriff. Dieser Bereich ist nur für Creator/Admin sichtbar.</div>
          <div className="mt-4">
            <a href="/app/chat">
              <KianaButton variant="primary">Zurück zum Chat</KianaButton>
            </a>
          </div>
        </KianaCard>
      </div>
    )
  }

  return (
    <div className="max-w-5xl mx-auto grid gap-4">
      <KianaCard>
        <div className="text-lg font-semibold">📈 Monitoring</div>
        <div className="small mt-1">System-Überwachung und Dashboards.</div>
      </KianaCard>

      <KianaCard>
        <div className="font-semibold mb-2">Dashboards</div>
        <div className="small mb-3">Öffnet in neuem Tab.</div>
        <div className="flex gap-3 flex-wrap">
          <a className="kiana-btn kiana-btn-primary" href={grafanaUrl} target="_blank" rel="noreferrer">Grafana</a>
          <a className="kiana-btn" href={prometheusUrl} target="_blank" rel="noreferrer">Prometheus</a>
        </div>
      </KianaCard>
    </div>
  )
}
