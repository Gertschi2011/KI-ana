'use client'

import { useEffect, useMemo, useState, type ChangeEvent } from 'react'
import KianaCard from '../../../components/ui/KianaCard'
import KianaButton from '../../../components/ui/KianaButton'

type BlockItem = {
  id: string
  title?: string
  topic?: string
  origin?: string
  source?: string
  timestamp?: string
  valid?: boolean
  sig_valid?: boolean
}

export default function BlockViewerPage() {
  const [loading, setLoading] = useState<boolean>(true)
  const [err, setErr] = useState<string | null>(null)
  const [canView, setCanView] = useState<boolean>(false)
  const [canRehash, setCanRehash] = useState<boolean>(false)

  const [busyRehash, setBusyRehash] = useState<boolean>(false)
  const [toast, setToast] = useState<string | null>(null)

  const [page, setPage] = useState<number>(1)
  const [limit] = useState<number>(50)
  const [includeUnverified, setIncludeUnverified] = useState<boolean>(false)
  const [total, setTotal] = useState<number>(0)
  const [count, setCount] = useState<number>(0)
  const [pages, setPages] = useState<number>(1)
  const [items, setItems] = useState<BlockItem[]>([])

  const [healthBusy, setHealthBusy] = useState<boolean>(false)
  const [healthInfo, setHealthInfo] = useState<any>(null)

  const hasPrev = page > 1
  const hasNext = page < pages

  const header = useMemo(() => {
    return includeUnverified ? 'Block Viewer (inkl. unverified)' : 'Block Viewer'
  }, [includeUnverified])

  async function load() {
    setLoading(true)
    setErr(null)
    try {
      const r = await fetch('/api/me', { credentials: 'include', cache: 'no-store' })
      const me = await r.json().catch(() => ({} as any))
      const u: any = me?.auth ? me?.user : null
      const role = String(u?.role ?? '').toLowerCase()
      const roles = Array.isArray(u?.roles) ? u.roles.map((x: any) => String(x).toLowerCase()) : []
      const isCreator = Boolean(u?.is_creator) || roles.includes('creator') || role === 'creator'
      const capsObj = (me?.caps && typeof me.caps === 'object') ? me.caps : ((u?.caps && typeof u.caps === 'object') ? u.caps : {})
      const allowed = Boolean(capsObj?.can_view_block_viewer) || isCreator
      const rehashAllowed = Boolean(capsObj?.can_rehash_blocks) || isCreator
      setCanView(allowed)
      setCanRehash(rehashAllowed)
      if (!allowed) {
        setItems([])
        setTotal(0)
        setCount(0)
        setPages(1)
        setErr('Kein Zugriff. Dieser Bereich ist nur für Creator sichtbar.')
        return
      }

      const qs = new URLSearchParams({
        page: String(page),
        limit: String(limit),
        include_unverified: includeUnverified ? 'true' : 'false',
      })
      const res = await fetch(`/api/blocks?${qs.toString()}`, { credentials: 'include', cache: 'no-store' })
      if (!res.ok) {
        const t = await res.text().catch(() => '')
        throw new Error(`Blocks konnten nicht geladen werden (${res.status})${t ? `: ${t}` : ''}`)
      }
      const data: any = await res.json().catch(() => ({}))
      setTotal(Number(data?.total || 0))
      setCount(Number(data?.count || 0))
      setPages(Number(data?.pages || 1))
      setItems(Array.isArray(data?.items) ? (data.items as BlockItem[]) : [])
    } catch (e: any) {
      setItems([])
      setTotal(0)
      setCount(0)
      setPages(1)
      setErr(typeof e?.message === 'string' ? e.message : 'Fehler beim Laden')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, includeUnverified])

  async function runRehash() {
    setToast(null)
    setBusyRehash(true)
    try {
      const res = await fetch('/api/blocks/rehash', {
        method: 'POST',
        credentials: 'include',
        headers: { 'content-type': 'application/json' },
        body: JSON.stringify({}),
      })
      const data: any = await res.json().catch(() => ({}))
      if (!res.ok || !data?.ok) {
        const msg = data?.error || `Rehash fehlgeschlagen (${res.status})`
        throw new Error(msg)
      }
      const n = Number(data?.count || 0)
      const errors = Array.isArray(data?.errors) ? data.errors : []
      setToast(`Rehash fertig: ${n} Block(s) aktualisiert.${errors.length ? ` (${errors.length} Fehler)` : ''}`)
      await load()
    } catch (e: any) {
      setToast(typeof e?.message === 'string' ? e.message : 'Rehash fehlgeschlagen')
    } finally {
      setBusyRehash(false)
    }
  }

  async function checkHealth() {
    setToast(null)
    setHealthBusy(true)
    try {
      const res = await fetch('/viewer/api/blocks/health', { credentials: 'include', cache: 'no-store' })
      const data: any = await res.json().catch(() => ({}))
      if (!res.ok || !data?.ok) {
        const msg = data?.error || data?.detail || `Health fehlgeschlagen (${res.status})`
        throw new Error(msg)
      }
      setHealthInfo(data)
      const okPct = data?.stats?.verified_ok_percent
      const totalN = data?.stats?.total
      setToast(`Health ok. verified_ok_percent=${okPct ?? '–'}% (total=${totalN ?? '–'})`)
    } catch (e: any) {
      setHealthInfo(null)
      setToast(typeof e?.message === 'string' ? e.message : 'Health fehlgeschlagen')
    } finally {
      setHealthBusy(false)
    }
  }

  function exportBlocks() {
    try {
      window.open('/api/export/blocks', '_blank', 'noopener,noreferrer')
    } catch {
      window.location.href = '/api/export/blocks'
    }
  }

  if (!canView && !loading) {
    return (
      <div className="max-w-6xl mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">Block Viewer</div>
          <div className="small mt-1">{err || 'Kein Zugriff.'}</div>
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
    <div className="max-w-6xl mx-auto grid gap-4">
      <KianaCard>
        <div className="flex items-start justify-between gap-4 flex-wrap">
          <div>
            <div className="text-lg font-semibold">{header}</div>
            <div className="small mt-1">
              Total: {total} • Seite {page}/{pages} • Items: {items.length}{count ? ` (count=${count})` : ''}
            </div>
          </div>
          <div className="flex gap-2 flex-wrap items-center">
            <label className="small" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <input
                type="checkbox"
                checked={includeUnverified}
                onChange={(e: ChangeEvent<HTMLInputElement>) => {
                  setPage(1)
                  setIncludeUnverified(e.target.checked)
                }}
              />
              Unverified anzeigen
            </label>
            <KianaButton variant="ghost" onClick={() => load()} disabled={loading}>
              Aktualisieren
            </KianaButton>
            <KianaButton variant="ghost" onClick={checkHealth} disabled={healthBusy || loading}>
              {healthBusy ? 'Health …' : 'Health'}
            </KianaButton>
            <KianaButton variant="ghost" onClick={exportBlocks} disabled={loading}>
              Export
            </KianaButton>
            <KianaButton variant="primary" onClick={runRehash} disabled={!canRehash || busyRehash}>
              {busyRehash ? 'Rehash …' : 'Rehash (creator)'}
            </KianaButton>
          </div>
        </div>

        {err ? (
          <div className="kiana-inset mt-4" role="status">
            <div className="font-semibold">Kurz notiert</div>
            <div className="small mt-1">{err}</div>
          </div>
        ) : null}

        {toast ? (
          <div className="mt-3 kiana-alert" role="status">
            <div className="small">{toast}</div>
          </div>
        ) : null}

        {healthInfo ? (
          <div className="kiana-inset mt-4" role="status">
            <div className="font-semibold">Health Details</div>
            <pre className="mt-2 text-xs whitespace-pre-wrap">{JSON.stringify(healthInfo, null, 2)}</pre>
          </div>
        ) : null}

        <div className="mt-4 overflow-x-auto">
          <table className="kiana-table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Titel/Topic</th>
                <th>Origin</th>
                <th>Valid</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr>
                  <td colSpan={4} className="small">Lade Blöcke…</td>
                </tr>
              ) : items.length === 0 ? (
                <tr>
                  <td colSpan={4} className="small">Keine Blöcke gefunden.</td>
                </tr>
              ) : (
                items.map((it: BlockItem) => (
                  <tr key={it.id}>
                    <td className="font-mono" style={{ fontSize: 12 }}>{it.id}</td>
                    <td>
                      <div className="font-medium">{it.title || it.topic || '–'}</div>
                      <div className="small" style={{ opacity: 0.75 }}>{it.source || ''}</div>
                    </td>
                    <td className="small">{it.origin || '–'}</td>
                    <td className="small">{(it.valid && it.sig_valid) ? 'ok' : 'warn'}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        <div className="mt-4 flex items-center justify-between gap-2">
          <KianaButton variant="ghost" disabled={!hasPrev || loading} onClick={() => setPage((p: number) => Math.max(1, p - 1))}>
            ← Zurück
          </KianaButton>
          <div className="small">Seite {page} von {pages}</div>
          <KianaButton variant="ghost" disabled={!hasNext || loading} onClick={() => setPage((p: number) => p + 1)}>
            Weiter →
          </KianaButton>
        </div>
      </KianaCard>
    </div>
  )
}
