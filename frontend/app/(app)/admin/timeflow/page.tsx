'use client'
import { useEffect, useState } from 'react'
import KianaCard from '../../../../components/ui/KianaCard'
import KianaButton from '../../../../components/ui/KianaButton'

interface TimeFlowState {
  tick: number
  ts_ms: number
  activation: number
  emotion: number
  subjective_time: number
  events_per_min: number
  reqs_per_min: number
  circadian_factor: number
}

interface TimeFlowConfig {
  interval_sec: number
  activation_decay: number
  stimulus_weight: number
  circadian_enabled: boolean
  circadian_amplitude: number
  alert_activation_warn: number
  alert_activation_crit: number
  alert_reqs_per_min_warn: number
  alert_reqs_per_min_crit: number
}

export default function TimeFlowManagerPage() {
  const [access, setAccess] = useState<'loading' | 'denied' | 'allowed'>('loading')
  const [state, setState] = useState<TimeFlowState | null>(null)
  const [config, setConfig] = useState<TimeFlowConfig | null>(null)
  const [alerts, setAlerts] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)

  // Access gate + auto-refresh every 2 seconds (Creator/Admin)
  useEffect(() => {
    let mounted = true
    let interval: any = null

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
        if (!allowed) {
          setLoading(false)
          return
        }

        await loadData()
        interval = setInterval(loadData, 2000)
      } catch {
        if (!mounted) return
        setAccess('denied')
        setLoading(false)
      }
    })()

    return () => {
      mounted = false
      if (interval) clearInterval(interval)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  async function loadData() {
    try {
      setLoading(true)
      
      // Load state
      const stateRes = await fetch('/api/timeflow/', {
        credentials: 'include'
      })
      if (stateRes.ok) {
        const data = await stateRes.json()
        setState(data.timeflow)
      }

      // Load config
      const configRes = await fetch('/api/timeflow/config', {
        credentials: 'include'
      })
      if (configRes.ok) {
        const data = await configRes.json()
        setConfig(data.config)
      }

      // Load alerts
      const alertsRes = await fetch('/api/timeflow/alerts?limit=10', {
        credentials: 'include'
      })
      if (alertsRes.ok) {
        const data = await alertsRes.json()
        setAlerts(data.alerts || [])
      }

      // Load stats
      const statsRes = await fetch('/api/timeflow/stats', {
        credentials: 'include'
      })
      if (statsRes.ok) {
        const data = await statsRes.json()
        setStats(data.stats)
      }

      setError(null)
    } catch (err) {
      setError('Fehler beim Laden der TimeFlow-Daten')
    } finally {
      setLoading(false)
    }
  }

  async function saveConfig() {
    if (!config) return
    
    try {
      const res = await fetch('/api/timeflow/config', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify(config)
      })

      if (res.ok) {
        setSaveMessage('✅ Konfiguration gespeichert')
        setTimeout(() => setSaveMessage(null), 3000)
      } else {
        setSaveMessage('❌ Fehler beim Speichern')
      }
    } catch (err) {
      setSaveMessage('❌ Fehler beim Speichern')
    }
  }

  function formatTimestamp(ts_ms: number) {
    return new Date(ts_ms).toLocaleString('de-DE')
  }

  function formatDuration(seconds: number) {
    const hours = Math.floor(seconds / 3600)
    const mins = Math.floor((seconds % 3600) / 60)
    const secs = Math.floor(seconds % 60)
    return `${hours}h ${mins}m ${secs}s`
  }

  if (access === 'loading') {
    return (
      <div className="max-w-7xl mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">TimeFlow</div>
          <div className="small mt-1">Prüfe Zugriff…</div>
        </KianaCard>
      </div>
    )
  }

  if (access === 'denied') {
    return (
      <div className="max-w-7xl mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">TimeFlow</div>
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

  if (loading && !state) {
    return (
      <div className="max-w-7xl mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">TimeFlow</div>
          <div className="small mt-1">Lade Daten…</div>
        </KianaCard>
      </div>
    )
  }

  if (error && !state) {
    return (
      <div className="max-w-7xl mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">TimeFlow</div>
          <div className="small mt-1">Konnte Daten nicht laden.</div>
          <div className="kiana-inset mt-4" role="status">
            <div className="font-semibold">Kurz notiert</div>
            <div className="small mt-1">{error}</div>
          </div>
          <div className="mt-4">
            <KianaButton variant="primary" onClick={loadData}>
              Erneut versuchen
            </KianaButton>
          </div>
        </KianaCard>
      </div>
    )
  }

  return (
    <div className="max-w-7xl mx-auto grid gap-6">
      <KianaCard>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="text-lg font-semibold">TimeFlow</div>
            <div className="small mt-1">Status, Konfiguration und Hinweise – ruhig und übersichtlich.</div>
          </div>
          <KianaButton onClick={loadData} variant="primary" disabled={loading}>
            Aktualisieren
          </KianaButton>
        </div>

        {error ? (
          <div className="kiana-inset mt-4" role="status">
            <div className="font-semibold">Kurz notiert</div>
            <div className="small mt-1">{error}</div>
          </div>
        ) : null}

        {state ? (
          <div className="kiana-inset mt-5">
            <h2 className="text-base font-semibold">Aktueller Status</h2>

            <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="small" style={{ opacity: 0.8 }}>Tick</div>
                <div className="text-2xl font-extrabold">{state.tick.toLocaleString()}</div>
              </div>
              <div>
                <div className="small" style={{ opacity: 0.8 }}>Activation</div>
                <div className="text-2xl font-extrabold">{(state.activation * 100).toFixed(1)}%</div>
                <div className="kiana-progress mt-2">
                  <div className="kiana-progress-bar" style={{ width: `${Math.max(0, Math.min(100, state.activation * 100))}%` }} />
                </div>
              </div>
              <div>
                <div className="small" style={{ opacity: 0.8 }}>Emotion</div>
                <div className="text-2xl font-extrabold">{(state.emotion * 100).toFixed(1)}%</div>
                <div className="kiana-progress mt-2" style={{ background: 'rgba(181,124,255,0.10)' }}>
                  <div
                    className="kiana-progress-bar"
                    style={{ width: `${Math.max(0, Math.min(100, state.emotion * 100))}%`, background: 'linear-gradient(90deg, rgba(181,124,255,0.9), rgba(123,140,255,0.9))' }}
                  />
                </div>
              </div>
              <div>
                <div className="small" style={{ opacity: 0.8 }}>Subjektive Zeit</div>
                <div className="text-2xl font-extrabold">{formatDuration(state.subjective_time)}</div>
              </div>
            </div>

            <div className="mt-5" style={{ height: 1, background: 'rgba(17,24,39,0.10)' }} />

            <div className="mt-4 grid grid-cols-2 md:grid-cols-4 gap-4">
              <div>
                <div className="small" style={{ opacity: 0.8 }}>Events/min</div>
                <div className="text-lg font-semibold">{state.events_per_min.toFixed(1)}</div>
              </div>
              <div>
                <div className="small" style={{ opacity: 0.8 }}>Requests/min</div>
                <div className="text-lg font-semibold">{state.reqs_per_min.toFixed(1)}</div>
              </div>
              <div>
                <div className="small" style={{ opacity: 0.8 }}>Circadian</div>
                <div className="text-lg font-semibold">{state.circadian_factor.toFixed(2)}</div>
              </div>
              <div>
                <div className="small" style={{ opacity: 0.8 }}>Timestamp</div>
                <div className="small">{formatTimestamp(state.ts_ms)}</div>
              </div>
            </div>
          </div>
        ) : (
          <div className="kiana-inset mt-5">
            <div className="font-semibold">Noch kein Status</div>
            <div className="small mt-1">Sobald TimeFlow aktiv ist, erscheint hier ein ruhiger Überblick.</div>
          </div>
        )}

        <div className="mt-5 grid md:grid-cols-2 gap-4">
          {config ? (
            <div className="kiana-inset">
              <h2 className="text-base font-semibold">Konfiguration</h2>

              <div className="mt-4 grid gap-3">
                <label className="block">
                  <div className="text-sm font-medium mb-1">Activation Decay</div>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={config.activation_decay}
                    onChange={e => setConfig({...config, activation_decay: parseFloat(e.target.value)})}
                    className="input"
                  />
                  <div className="small mt-1">Wie schnell die Aktivierung abklingt (0–1).</div>
                </label>

                <label className="block">
                  <div className="text-sm font-medium mb-1">Stimulus Weight</div>
                  <input
                    type="number"
                    step="0.01"
                    min="0"
                    max="1"
                    value={config.stimulus_weight}
                    onChange={e => setConfig({...config, stimulus_weight: parseFloat(e.target.value)})}
                    className="input"
                  />
                  <div className="small mt-1">Gewicht für neue Stimuli.</div>
                </label>

                <label className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    checked={config.circadian_enabled}
                    onChange={e => setConfig({...config, circadian_enabled: e.target.checked})}
                    className="w-4 h-4"
                  />
                  <div className="text-sm font-medium">Circadian Rhythm aktiviert</div>
                </label>

                {config.circadian_enabled && (
                  <label className="block">
                    <div className="text-sm font-medium mb-1">Circadian Amplitude</div>
                    <input
                      type="number"
                      step="0.05"
                      min="0"
                      max="1"
                      value={config.circadian_amplitude}
                      onChange={e => setConfig({...config, circadian_amplitude: parseFloat(e.target.value)})}
                      className="input"
                    />
                  </label>
                )}

                <div className="pt-3" style={{ borderTop: '1px solid rgba(17,24,39,0.10)' }}>
                  <h3 className="font-medium mb-2">Alert Thresholds</h3>

                  <label className="block mb-2">
                    <div className="text-sm mb-1">Activation Warning</div>
                    <input
                      type="number"
                      step="0.05"
                      min="0"
                      max="1"
                      value={config.alert_activation_warn}
                      onChange={e => setConfig({...config, alert_activation_warn: parseFloat(e.target.value)})}
                      className="input"
                    />
                  </label>

                  <label className="block mb-2">
                    <div className="text-sm mb-1">Activation Critical</div>
                    <input
                      type="number"
                      step="0.05"
                      min="0"
                      max="1"
                      value={config.alert_activation_crit}
                      onChange={e => setConfig({...config, alert_activation_crit: parseFloat(e.target.value)})}
                      className="input"
                    />
                  </label>

                  <label className="block mb-2">
                    <div className="text-sm mb-1">Requests/min Warning</div>
                    <input
                      type="number"
                      step="10"
                      min="0"
                      value={config.alert_reqs_per_min_warn}
                      onChange={e => setConfig({...config, alert_reqs_per_min_warn: parseFloat(e.target.value)})}
                      className="input"
                    />
                  </label>

                  <label className="block mb-2">
                    <div className="text-sm mb-1">Requests/min Critical</div>
                    <input
                      type="number"
                      step="10"
                      min="0"
                      value={config.alert_reqs_per_min_crit}
                      onChange={e => setConfig({...config, alert_reqs_per_min_crit: parseFloat(e.target.value)})}
                      className="input"
                    />
                  </label>
                </div>

                <div className="mt-1">
                  <KianaButton variant="primary" onClick={saveConfig}>
                    Konfiguration speichern
                  </KianaButton>
                </div>

                {saveMessage ? (
                  <div className="kiana-inset mt-3" role="status">
                    <div className="small">{saveMessage.replace('✅', '').replace('❌', '').trim()}</div>
                  </div>
                ) : null}
              </div>
            </div>
          ) : (
            <div className="kiana-inset">
              <div className="font-semibold">Konfiguration nicht verfügbar</div>
              <div className="small mt-1">Wenn der Endpunkt bereit ist, kannst du hier Werte anpassen.</div>
            </div>
          )}

          <div className="grid gap-4">
            <div className="kiana-inset">
              <h2 className="text-base font-semibold">Kürzliche Alerts</h2>
              {alerts.length === 0 ? (
                <div className="small mt-2" style={{ opacity: 0.8 }}>Im Moment ist alles ruhig.</div>
              ) : (
                <div className="mt-3 grid gap-2">
                  {alerts.map((alert, idx) => (
                    <div key={idx} className="rounded-xl p-3" style={{ background: 'rgba(255,255,255,0.70)', border: '1px solid rgba(17,24,39,0.08)' }}>
                      <div className="flex justify-between items-start gap-4">
                        <div className="font-medium">{alert.kind}</div>
                        <div className="small" style={{ opacity: 0.7 }}>{formatTimestamp(alert.ts)}</div>
                      </div>
                      {alert.severity ? (
                        <div className="small mt-1" style={{ opacity: 0.85 }}>
                          Severity: {String(alert.severity)}
                        </div>
                      ) : null}
                    </div>
                  ))}
                </div>
              )}
            </div>

            {stats ? (
              <div className="kiana-inset">
                <h2 className="text-base font-semibold">Statistiken</h2>
                <div className="mt-3 grid gap-2">
                  <div className="flex justify-between gap-4">
                    <span className="small" style={{ opacity: 0.85 }}>Webhook Dropped Total</span>
                    <span className="font-semibold">{stats.webhook_dropped_total}</span>
                  </div>
                  <div className="flex justify-between gap-4">
                    <span className="small" style={{ opacity: 0.85 }}>Pruned Files Total</span>
                    <span className="font-semibold">{stats.pruned_files_total}</span>
                  </div>
                  {stats.last_compact_ts > 0 ? (
                    <div className="flex justify-between gap-4">
                      <span className="small" style={{ opacity: 0.85 }}>Last Compaction</span>
                      <span className="font-semibold">{formatTimestamp(stats.last_compact_ts * 1000)}</span>
                    </div>
                  ) : null}
                </div>
              </div>
            ) : (
              <div className="kiana-inset">
                <div className="font-semibold">Noch keine Statistiken</div>
                <div className="small mt-1">Wenn TimeFlow Stats liefert, tauchen sie hier automatisch auf.</div>
              </div>
            )}
          </div>
        </div>
      </KianaCard>
    </div>
  )
}
