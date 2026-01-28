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

type AddressbookTree = Record<string, Record<string, string[]>>

type AddressbookResponse = {
  ok: boolean
  path?: string
  exists?: boolean
  readable?: boolean
  topics_count?: number
  entries_count?: number
  last_rebuild_ts?: number | null
  filtered?: boolean
  tree?: AddressbookTree
}

export default function BlockViewerPage() {
  const [loading, setLoading] = useState<boolean>(true)
  const [err, setErr] = useState<string | null>(null)
  const [canView, setCanView] = useState<boolean>(false)
  const [canRehash, setCanRehash] = useState<boolean>(false)
  const [isAdminLike, setIsAdminLike] = useState<boolean>(false)

  const [view, setView] = useState<'blocks' | 'addressbook'>('blocks')

  const [busyRehash, setBusyRehash] = useState<boolean>(false)
  const [toast, setToast] = useState<string | null>(null)

  const [page, setPage] = useState<number>(1)
  const [limit] = useState<number>(50)
  const [includeUnverified, setIncludeUnverified] = useState<boolean>(false)
  const [source, setSource] = useState<'filesystem'|'addressbook'>('filesystem')
  const [total, setTotal] = useState<number>(0)
  const [count, setCount] = useState<number>(0)
  const [pages, setPages] = useState<number>(1)
  const [items, setItems] = useState<BlockItem[]>([])

  const [healthBusy, setHealthBusy] = useState<boolean>(false)
  const [healthInfo, setHealthInfo] = useState<any>(null)

  const [healthSummaryBusy, setHealthSummaryBusy] = useState<boolean>(false)
  const [healthSummary, setHealthSummary] = useState<any>(null)
  const [coverageBusy, setCoverageBusy] = useState<boolean>(false)
  const [coverageInfo, setCoverageInfo] = useState<any>(null)
  const [coverageErr, setCoverageErr] = useState<string | null>(null)

  const [abLoading, setAbLoading] = useState<boolean>(false)
  const [abErr, setAbErr] = useState<string | null>(null)
  const [abSearch, setAbSearch] = useState<string>('')
  const [abData, setAbData] = useState<AddressbookResponse | null>(null)
  const [abExpandedCats, setAbExpandedCats] = useState<Record<string, boolean>>({})
  const [abExpandedTopics, setAbExpandedTopics] = useState<Record<string, boolean>>({})

  const hasPrev = page > 1
  const hasNext = page < pages

  const filterLabel = includeUnverified ? 'Including unverified' : 'Verified only'
  const healthTotal = Number(healthSummary?.stats?.total ?? 0) || 0
  const healthVerified = Number(healthSummary?.stats?.signature_ok ?? 0) || 0
  const healthUnverified = Math.max(0, healthTotal - healthVerified)

  const header = useMemo(() => {
    return includeUnverified ? 'Block Viewer (inkl. unverified)' : 'Block Viewer'
  }, [includeUnverified])

  function fmtTs(ts: number | null | undefined): string {
    if (!ts) return '–'
    try {
      return new Date(ts * 1000).toLocaleString()
    } catch {
      return String(ts)
    }
  }

  async function loadAddressbook() {
    setAbLoading(true)
    setAbErr(null)
    try {
      const qs = new URLSearchParams()
      if (abSearch.trim()) qs.set('q', abSearch.trim())
      const res = await fetch(`/viewer/api/addressbook?${qs.toString()}`, { credentials: 'include', cache: 'no-store' })
      const data: any = await res.json().catch(() => ({}))
      if (!res.ok || !data?.ok) {
        const msg = data?.error || data?.detail || `Adressbuch konnte nicht geladen werden (${res.status})`
        throw new Error(msg)
      }
      setAbData(data as AddressbookResponse)
    } catch (e: any) {
      setAbData(null)
      setAbErr(typeof e?.message === 'string' ? e.message : 'Fehler beim Laden')
    } finally {
      setAbLoading(false)
    }
  }

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
      const isAdmin = roles.includes('admin') || role === 'admin'
      const capsObj = (me?.caps && typeof me.caps === 'object') ? me.caps : ((u?.caps && typeof u.caps === 'object') ? u.caps : {})
      const allowed = Boolean(capsObj?.can_view_block_viewer) || isCreator
      const rehashAllowed = Boolean(capsObj?.can_rehash_blocks) || isCreator
      setCanView(allowed)
      setCanRehash(rehashAllowed)
      setIsAdminLike(Boolean(isAdmin || isCreator))
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
        verified_only: includeUnverified ? 'false' : 'true',
        source: source,
      })
      const res = await fetch(`/viewer/api/blocks?${qs.toString()}`, { credentials: 'include', cache: 'no-store' })
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

  async function loadVerificationSummary() {
    if (!isAdminLike) return
    setCoverageErr(null)
    setCoverageBusy(true)
    setHealthSummaryBusy(true)
    try {
      const [rh, rc] = await Promise.all([
        fetch('/viewer/api/blocks/health', { credentials: 'include', cache: 'no-store' }),
        fetch('/viewer/api/blocks/coverage', { credentials: 'include', cache: 'no-store' }),
      ])
      const jh: any = await rh.json().catch(() => ({}))
      const jc: any = await rc.json().catch(() => ({}))
      if (rh.ok && jh?.ok) setHealthSummary(jh)
      if (rc.ok && jc?.ok) setCoverageInfo(jc)
      if ((!rc.ok || !jc?.ok) && (jc?.error || jc?.detail)) setCoverageErr(String(jc?.error || jc?.detail))
    } catch (e: any) {
      setCoverageErr(typeof e?.message === 'string' ? e.message : 'Summary konnte nicht geladen werden')
    } finally {
      setCoverageBusy(false)
      setHealthSummaryBusy(false)
    }
  }

  useEffect(() => {
    if (view === 'blocks') {
      load()
    } else {
      loadAddressbook()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [page, includeUnverified, view, source])

  useEffect(() => {
    if (view !== 'blocks') return
    if (!includeUnverified) return
    // When showing unverified, proactively fetch a short explanation (stats + coverage)
    loadVerificationSummary()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view, includeUnverified, source, isAdminLike])

  useEffect(() => {
    if (view !== 'addressbook') return
    const t = setTimeout(() => {
      loadAddressbook()
    }, 250)
    return () => clearTimeout(t)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [abSearch])

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
            <div className="small mt-1" style={{ opacity: 0.85 }}>
              Filter: <b>{filterLabel}</b>
              {includeUnverified && healthSummary?.stats ? (
                <> • Verified: {healthVerified} / Unverified: {healthUnverified}</>
              ) : null}
            </div>
            {includeUnverified && source === 'filesystem' ? (
              <div className="small mt-2" style={{ opacity: 0.9 }}>
                Hinweis: <b>Unverified anzeigen</b> listet alle Block-Dateien im Filesystem.
                <span style={{ opacity: 0.85 }}> Verified-only filtert strikt auf <code>sig_valid && valid</code>.</span>
                <div className="mt-2" style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
                  <span>Health total={healthSummary?.stats?.total ?? '–'}</span>
                  <span>hash_ok={healthSummary?.stats?.hash_ok ?? '–'}</span>
                  <span>signature_ok={healthSummary?.stats?.signature_ok ?? '–'}</span>
                  <span>Adressbuch={coverageInfo?.addressbook_count ?? '–'}</span>
                  <span>FS={coverageInfo?.fs_total ?? '–'}</span>
                  <span>diff={coverageInfo?.diff ?? '–'}</span>
                </div>
                {coverageErr ? <div className="mt-1" style={{ color: 'var(--danger, #b91c1c)' }}>{coverageErr}</div> : null}
                <div className="mt-2">
                  <KianaButton variant="ghost" onClick={loadVerificationSummary} disabled={coverageBusy || healthSummaryBusy}>
                    {coverageBusy || healthSummaryBusy ? 'Erklärung …' : 'Erklärung aktualisieren'}
                  </KianaButton>
                </div>
              </div>
            ) : null}
          </div>
          <div className="flex gap-2 flex-wrap items-center">
            <div className="flex gap-1 items-center">
              <KianaButton variant={view === 'blocks' ? 'primary' : 'ghost'} onClick={() => { setView('blocks'); setPage(1) }}>
                Blöcke
              </KianaButton>
              <KianaButton variant={view === 'addressbook' ? 'primary' : 'ghost'} onClick={() => { setView('addressbook'); setPage(1) }}>
                📚 Adressbuch
              </KianaButton>
            </div>
            <div className="small" style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              Quelle:
              <select value={source} onChange={(e) => { setSource(e.target.value as any); setPage(1); }} className="ml-1">
                <option value="filesystem">Filesystem (default)</option>
                <option value="addressbook">Addressbook (index)</option>
              </select>
            </div>
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
            {/* Debug: coverage & rebuild - visible to creators only (canRehash true) */}
            {canRehash ? (
              <>
                <KianaButton variant="ghost" onClick={async () => {
                  try {
                    const r = await fetch('/viewer/api/blocks/coverage', { credentials: 'include' })
                    const j = await r.json()
                    if (r.ok && j?.ok) {
                      setToast(`Coverage: fs=${j.fs_total} ab=${j.addressbook_count} diff=${j.diff}`)
                    } else {
                      setToast(j?.error || 'Coverage failed')
                    }
                  } catch (e) { setToast('Coverage failed') }
                }}>
                  Coverage
                </KianaButton>
                <KianaButton variant="secondary" onClick={async () => {
                  if (!confirm('Rebuild addressbook from filesystem? This will overwrite index.')) return
                  try {
                    const r = await fetch('/viewer/api/rebuild-addressbook', { method: 'POST', credentials: 'include' })
                    const j = await r.json()
                    if (r.ok && j?.ok) {
                      setToast(`Rebuild ok: topics=${j.topics_count} entries=${j.entries_count} took_ms=${j.took_ms}`)
                      if (view === 'blocks') {
                        await load()
                      } else {
                        await loadAddressbook()
                      }
                    } else {
                      setToast(j?.error || 'Rebuild failed')
                    }
                  } catch (e) { setToast('Rebuild failed') }
                }}>
                  Rebuild Index
                </KianaButton>
              </>
            ) : null}
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

        {view === 'blocks' ? (
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
        ) : (
          <div className="mt-4">
            <div className="kiana-inset" role="status">
              <div className="font-semibold">📚 Adressbuch</div>
              <div className="small mt-1">
                Topics: {abData?.topics_count ?? '–'} • Einträge: {abData?.entries_count ?? '–'} • letzter Rebuild: {fmtTs(abData?.last_rebuild_ts ?? null)}
              </div>
              <div className="mt-3 flex gap-2 flex-wrap items-center">
                <input
                  value={abSearch}
                  onChange={(e) => setAbSearch(e.target.value)}
                  placeholder="Suche Topic/Tag/Block-ID…"
                  className="kiana-input"
                  style={{ minWidth: 260 }}
                />
                <KianaButton variant="ghost" onClick={loadAddressbook} disabled={abLoading}>
                  {abLoading ? 'Lade…' : 'Reload'}
                </KianaButton>
                {isAdminLike ? (
                  <KianaButton variant="secondary" onClick={async () => {
                    if (!confirm('Rebuild Adressbuch? (überschreibt addressbook.json)')) return
                    try {
                      const r = await fetch('/viewer/api/rebuild-addressbook', { method: 'POST', credentials: 'include' })
                      const j = await r.json()
                      if (r.ok && j?.ok) {
                        setToast(`Rebuild ok: topics=${j.topics_count} entries=${j.entries_count} took_ms=${j.took_ms}`)
                        await loadAddressbook()
                      } else {
                        setToast(j?.error || 'Rebuild failed')
                      }
                    } catch {
                      setToast('Rebuild failed')
                    }
                  }}>
                    🔁 Rebuild Adressbuch
                  </KianaButton>
                ) : null}
              </div>
              {abErr ? <div className="small mt-2">{abErr}</div> : null}
            </div>

            <div className="mt-4">
              {abLoading ? (
                <div className="small">Lade Adressbuch…</div>
              ) : !abData?.tree ? (
                <div className="small">Keine Daten.</div>
              ) : (
                <div className="grid gap-2">
                  {Object.keys(abData.tree).sort().map((cat) => {
                    const topicsObj = abData.tree?.[cat] || {}
                    const catOpen = Boolean(abExpandedCats[cat])
                    const topics = Object.keys(topicsObj).sort()
                    return (
                      <div key={cat} className="kiana-inset">
                        <button
                          className="w-full text-left"
                          onClick={() => setAbExpandedCats((s) => ({ ...s, [cat]: !catOpen }))}
                        >
                          <div className="font-semibold">{cat} <span className="small" style={{ opacity: 0.7 }}>({topics.length} Topics)</span></div>
                        </button>
                        {catOpen ? (
                          <div className="mt-2 grid gap-2">
                            {topics.map((topic) => {
                              const ids = topicsObj[topic] || []
                              const key = `${cat}::${topic}`
                              const open = Boolean(abExpandedTopics[key])
                              return (
                                <div key={key} className="kiana-inset">
                                  <button className="w-full text-left" onClick={() => setAbExpandedTopics((s) => ({ ...s, [key]: !open }))}>
                                    <div className="font-medium">{topic} <span className="small" style={{ opacity: 0.7 }}>({ids.length})</span></div>
                                  </button>
                                  {open ? (
                                    <div className="mt-2 flex flex-wrap gap-2">
                                      {ids.map((id) => (
                                        <span key={id} className="font-mono" style={{ fontSize: 12, opacity: 0.9 }}>{id}</span>
                                      ))}
                                    </div>
                                  ) : null}
                                </div>
                              )
                            })}
                          </div>
                        ) : null}
                      </div>
                    )
                  })}
                </div>
              )}
            </div>
          </div>
        )}

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
