'use client'
import { useEffect, useState } from 'react'

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
  const [state, setState] = useState<TimeFlowState | null>(null)
  const [config, setConfig] = useState<TimeFlowConfig | null>(null)
  const [alerts, setAlerts] = useState<any[]>([])
  const [stats, setStats] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [saveMessage, setSaveMessage] = useState<string | null>(null)

  // Auto-refresh every 2 seconds
  useEffect(() => {
    loadData()
    const interval = setInterval(loadData, 2000)
    return () => clearInterval(interval)
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
      console.error(err)
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
      console.error(err)
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

  if (loading && !state) {
    return (
      <div className="p-4">
        <h1 className="text-2xl font-bold mb-4">⏱️ TimeFlow Manager</h1>
        <div className="card">Lade Daten...</div>
      </div>
    )
  }

  if (error && !state) {
    return (
      <div className="p-4">
        <h1 className="text-2xl font-bold mb-4">⏱️ TimeFlow Manager</h1>
        <div className="card bg-red-50 text-red-600">{error}</div>
      </div>
    )
  }

  return (
    <div className="p-4 max-w-7xl mx-auto">
      <div className="flex items-center justify-between mb-6">
        <h1 className="text-3xl font-bold">⏱️ TimeFlow Manager</h1>
        <button onClick={loadData} className="btn-dark">
          🔄 Aktualisieren
        </button>
      </div>

      {/* Current State */}
      {state && (
        <div className="card mb-6">
          <h2 className="text-xl font-bold mb-4">Aktueller Status</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div>
              <div className="text-sm text-gray-600">Tick</div>
              <div className="text-2xl font-bold">{state.tick.toLocaleString()}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Activation</div>
              <div className="text-2xl font-bold">
                {(state.activation * 100).toFixed(1)}%
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                <div 
                  className="bg-blue-600 h-2 rounded-full" 
                  style={{ width: `${state.activation * 100}%` }}
                />
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Emotion</div>
              <div className="text-2xl font-bold">
                {(state.emotion * 100).toFixed(1)}%
              </div>
              <div className="w-full bg-gray-200 rounded-full h-2 mt-1">
                <div 
                  className="bg-purple-600 h-2 rounded-full" 
                  style={{ width: `${state.emotion * 100}%` }}
                />
              </div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Subjektive Zeit</div>
              <div className="text-2xl font-bold">
                {formatDuration(state.subjective_time)}
              </div>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mt-4 pt-4 border-t">
            <div>
              <div className="text-sm text-gray-600">Events/min</div>
              <div className="text-lg font-semibold">{state.events_per_min.toFixed(1)}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Requests/min</div>
              <div className="text-lg font-semibold">{state.reqs_per_min.toFixed(1)}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Circadian Factor</div>
              <div className="text-lg font-semibold">{state.circadian_factor.toFixed(2)}</div>
            </div>
            <div>
              <div className="text-sm text-gray-600">Timestamp</div>
              <div className="text-xs">{formatTimestamp(state.ts_ms)}</div>
            </div>
          </div>
        </div>
      )}

      <div className="grid md:grid-cols-2 gap-6">
        {/* Configuration */}
        {config && (
          <div className="card">
            <h2 className="text-xl font-bold mb-4">⚙️ Konfiguration</h2>
            <div className="grid gap-3">
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
                <div className="text-xs text-gray-500 mt-1">
                  Wie schnell die Aktivierung abklingt (0-1)
                </div>
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
                <div className="text-xs text-gray-500 mt-1">
                  Gewicht für neue Stimuli
                </div>
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

              <div className="pt-3 border-t">
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

              <button onClick={saveConfig} className="btn-dark mt-3">
                💾 Konfiguration speichern
              </button>

              {saveMessage && (
                <div className="text-sm p-2 bg-gray-100 rounded">
                  {saveMessage}
                </div>
              )}
            </div>
          </div>
        )}

        {/* Alerts & Stats */}
        <div className="space-y-6">
          {/* Recent Alerts */}
          <div className="card">
            <h2 className="text-xl font-bold mb-4">🚨 Kürzliche Alerts</h2>
            {alerts.length === 0 ? (
              <div className="text-sm text-gray-500">Keine Alerts</div>
            ) : (
              <div className="space-y-2">
                {alerts.map((alert, idx) => (
                  <div key={idx} className="p-2 bg-gray-50 rounded text-sm">
                    <div className="flex justify-between items-start">
                      <div className="font-medium">{alert.kind}</div>
                      <div className="text-xs text-gray-500">
                        {formatTimestamp(alert.ts)}
                      </div>
                    </div>
                    {alert.severity && (
                      <div className={`text-xs mt-1 ${
                        alert.severity === 'crit' ? 'text-red-600' : 'text-yellow-600'
                      }`}>
                        Severity: {alert.severity}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* System Stats */}
          {stats && (
            <div className="card">
              <h2 className="text-xl font-bold mb-4">📊 Statistiken</h2>
              <div className="space-y-2 text-sm">
                <div className="flex justify-between">
                  <span>Webhook Dropped Total:</span>
                  <span className="font-semibold">{stats.webhook_dropped_total}</span>
                </div>
                <div className="flex justify-between">
                  <span>Pruned Files Total:</span>
                  <span className="font-semibold">{stats.pruned_files_total}</span>
                </div>
                {stats.last_compact_ts > 0 && (
                  <div className="flex justify-between">
                    <span>Last Compaction:</span>
                    <span className="font-semibold">
                      {formatTimestamp(stats.last_compact_ts * 1000)}
                    </span>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
