'use client'

import { useEffect, useMemo, useRef, useState } from 'react'

type LiveEvent = {
  ts?: string
  kind?: string
  level?: string
  msg?: string
  path?: string
  size?: number
  owner?: string
  pid?: number | string
  user?: string
  cmd?: string
  container?: string
  [k: string]: any
}

export default function LiveLogPage() {
  const [status, setStatus] = useState<'connecting'|'connected'|'error'>('connecting')
  const [filter, setFilter] = useState<string>('')
  const [events, setEvents] = useState<LiveEvent[]>([])
  const esRef = useRef<EventSource | null>(null)

  const filtered = useMemo(() => {
    const q = filter.trim().toLowerCase()
    if (!q) return events
    return events.filter(e => {
      const hay = [e.kind, e.msg, e.path, e.cmd, e.container, e.pid]
        .map(x => String(x ?? '').toLowerCase())
        .join(' | ')
      return hay.includes(q)
    })
  }, [events, filter])

  useEffect(() => {
    let mounted = true

    async function loadTail() {
      try {
        const r = await fetch('/api/livelog/tail?limit=200', { credentials: 'include' })
        if (!r.ok) return
        const j = await r.json()
        const items = Array.isArray(j?.items) ? j.items : []
        if (mounted) {
          setEvents(items.slice(-200).reverse())
        }
      } catch {}
    }

    function connect() {
      try { esRef.current?.close() } catch {}
      setStatus('connecting')
      const es = new EventSource('/api/livelog/stream')
      esRef.current = es

      es.onopen = () => {
        if (!mounted) return
        setStatus('connected')
      }
      es.onerror = () => {
        if (!mounted) return
        setStatus('error')
      }
      es.onmessage = (ev) => {
        try {
          const e: LiveEvent = JSON.parse(ev.data)
          if (!mounted) return
          setEvents(prev => {
            const next = [e, ...prev]
            return next.slice(0, 400)
          })
        } catch {}
      }
    }

    loadTail()
    connect()

    return () => {
      mounted = false
      try { esRef.current?.close() } catch {}
    }
  }, [])

  const pill = status === 'connected'
    ? { bg: 'bg-emerald-50', fg: 'text-emerald-700', label: 'connected' }
    : status === 'connecting'
      ? { bg: 'bg-amber-50', fg: 'text-amber-700', label: 'connecting…' }
      : { bg: 'bg-rose-50', fg: 'text-rose-700', label: 'reconnecting…' }

  return (
    <div className="space-y-4">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">LiveLog</h1>
          <p className="text-sm text-slate-500">SSE Stream: <span className="font-mono">/api/livelog/stream</span></p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className={`px-3 py-1 rounded-full border ${pill.bg} ${pill.fg}`}>{pill.label}</span>
          <input
            className="px-3 py-2 rounded-xl border border-slate-200 min-w-[260px]"
            placeholder="Filter (kind/cmd/path)"
            value={filter}
            onChange={e => setFilter(e.target.value)}
          />
          <button
            className="px-3 py-2 rounded-xl bg-slate-900 text-white"
            onClick={() => setEvents([])}
          >
            Clear
          </button>
          <a className="px-3 py-2 rounded-xl bg-gradient-to-r from-violet-500 to-sky-400 text-white" href="/livelog">Legacy</a>
        </div>
      </div>

      <div className="bg-white border border-slate-200 rounded-2xl overflow-hidden">
        <div className="px-4 py-3 border-b border-slate-100 text-sm text-slate-600">Last events</div>
        <div className="overflow-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="text-left text-slate-500 border-b border-slate-100">
                <th className="p-3 w-[190px]">ts</th>
                <th className="p-3 w-[140px]">kind</th>
                <th className="p-3">details</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map((e, idx) => (
                <tr key={idx} className="border-b border-slate-50 align-top">
                  <td className="p-3 font-mono text-xs text-slate-500">{String(e.ts ?? '')}</td>
                  <td className="p-3"><span className="px-2 py-1 rounded-full bg-slate-100 text-slate-800">{String(e.kind ?? '')}</span></td>
                  <td className="p-3">
                    {e.msg ? <div className={String(e.level||'').toLowerCase()==='error' ? 'text-rose-700' : ''}>{String(e.msg)}</div> : null}
                    {e.path ? <div className="font-mono text-xs">path: {String(e.path)}</div> : null}
                    {e.cmd ? <div className="font-mono text-xs">cmd: {String(e.cmd)}</div> : null}
                    {e.pid != null ? <div className="font-mono text-xs">pid: {String(e.pid)}</div> : null}
                    {e.container ? <div className="font-mono text-xs">container: {String(e.container)}</div> : null}
                    {e.size != null ? <div className="font-mono text-xs">size: {String(e.size)}</div> : null}
                  </td>
                </tr>
              ))}
              {filtered.length === 0 ? (
                <tr>
                  <td className="p-4 text-slate-500" colSpan={3}>No events yet.</td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
