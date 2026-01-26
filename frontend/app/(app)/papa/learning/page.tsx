'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'
import KianaCard from '../../../../components/ui/KianaCard'
import KianaButton from '../../../../components/ui/KianaButton'

type Candidate = {
  candidate_id?: string
  status?: string
  topic?: string
  created_at?: number
  source?: string
  preview?: any
}

function formatTs(ts?: number) {
  if (!ts || typeof ts !== 'number') return null
  try {
    return new Date(ts * 1000).toLocaleString()
  } catch {
    return null
  }
}

export default function PapaLearningPage() {
  const [access, setAccess] = useState<'loading' | 'denied' | 'allowed'>('loading')
  const [status, setStatus] = useState<'pending' | 'accepted' | 'denied' | 'all'>('pending')
  const [items, setItems] = useState<Candidate[]>([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [busyId, setBusyId] = useState<string | null>(null)

  const title = useMemo(() => {
    switch (status) {
      case 'accepted':
        return 'Angenommen'
      case 'denied':
        return 'Abgelehnt'
      case 'all':
        return 'Alle'
      default:
        return 'Offen'
    }
  }, [status])

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
        if (!mounted) return
        setAccess(isCreator ? 'allowed' : 'denied')
      } catch {
        if (!mounted) return
        setAccess('denied')
      }
    })()
    return () => {
      mounted = false
    }
  }, [])

  async function load() {
    setLoading(true)
    setError(null)
    try {
      const r = await fetch(`/api/v2/learning/candidates?status=${encodeURIComponent(status)}&limit=200`, {
        credentials: 'include',
      })
      const j = await r.json().catch(() => ({} as any))
      const arr = Array.isArray(j?.items) ? j.items : []
      setItems(arr)
    } catch (e: any) {
      setError(e?.message || 'Fehler beim Laden')
      setItems([])
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (access !== 'allowed') return
    load()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [access, status])

  async function decide(candidateId: string, decision: 'accept' | 'deny') {
    setBusyId(candidateId)
    setError(null)
    try {
      const r = await fetch('/api/v2/learning/consent', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        credentials: 'include',
        body: JSON.stringify({ candidate_id: candidateId, decision }),
      })
      const j = await r.json().catch(() => ({} as any))
      if (!r.ok || j?.ok !== true) {
        throw new Error(j?.detail || 'Entscheidung fehlgeschlagen')
      }
      await load()
    } catch (e: any) {
      setError(e?.message || 'Entscheidung fehlgeschlagen')
    } finally {
      setBusyId(null)
    }
  }

  if (access === 'loading') {
    return (
      <div className="max-w-6xl mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">Learning Candidates</div>
          <div className="small mt-1">Prüfe Zugriff…</div>
        </KianaCard>
      </div>
    )
  }

  if (access === 'denied') {
    return (
      <div className="max-w-6xl mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">Learning Candidates</div>
          <div className="small mt-1">Kein Zugriff. Nur für Gerald (Creator).</div>
          <div className="mt-4">
            <Link href="/app/papa">
              <KianaButton variant="primary">Zurück zu Papa Tools</KianaButton>
            </Link>
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
            <div className="text-lg font-semibold">Learning Candidates</div>
            <div className="small mt-1">Dein „Ja/Nein“ macht KI_ana besser – ruhig, bewusst, nachvollziehbar.</div>
          </div>
          <div className="flex gap-2 flex-wrap">
            <Link href="/app/papa">
              <KianaButton variant="secondary">Papa Tools</KianaButton>
            </Link>
            <a href="/app/chat">
              <KianaButton variant="primary">Zum Chat</KianaButton>
            </a>
          </div>
        </div>

        <div className="kiana-inset mt-5">
          <div className="flex gap-2 flex-wrap items-center">
            <div className="small">Ansicht:</div>
            {(['pending', 'accepted', 'denied', 'all'] as const).map((s) => (
              <button
                key={s}
                onClick={() => setStatus(s)}
                className="px-3 py-1 rounded-full text-sm"
                style={{
                  border: '1px solid rgba(17,24,39,0.12)',
                  background: status === s ? 'rgba(147,51,234,0.10)' : 'rgba(255,255,255,0.6)',
                }}
              >
                {s === 'pending' ? 'Offen' : s === 'accepted' ? 'Angenommen' : s === 'denied' ? 'Abgelehnt' : 'Alle'}
              </button>
            ))}
            <div className="ml-auto">
              <button
                onClick={load}
                className="px-3 py-1 rounded-full text-sm"
                style={{ border: '1px solid rgba(17,24,39,0.12)', background: 'rgba(255,255,255,0.6)' }}
              >
                Aktualisieren
              </button>
            </div>
          </div>

          {error ? <div className="small mt-3" style={{ color: '#b91c1c' }}>{error}</div> : null}
          <div className="small mt-3">{loading ? 'Lade…' : `${items.length} Einträge (${title}).`}</div>
        </div>
      </KianaCard>

      {items.length === 0 ? (
        <KianaCard>
          <div className="font-semibold">Hier warten neue Gedanken auf dich ✨</div>
          <div className="small mt-1">Wenn KI_ana etwas lernen will, legt sie es hier ab – damit du entscheiden kannst.</div>
        </KianaCard>
      ) : (
        <div className="grid gap-3">
          {items.map((c) => {
            const cid = String(c?.candidate_id ?? '')
            const ts = formatTs(c?.created_at)
            return (
              <KianaCard key={cid || Math.random()}>
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div>
                    <div className="font-semibold">{c?.topic ? String(c.topic) : 'Ohne Topic'}</div>
                    <div className="small mt-1">
                      <span>Status: {String(c?.status ?? '–')}</span>
                      {ts ? <span> · {ts}</span> : null}
                      {c?.source ? <span> · Quelle: {String(c.source)}</span> : null}
                    </div>
                    {c?.preview?.content ? (
                      <div className="small mt-3" style={{ whiteSpace: 'pre-wrap' }}>
                        {String(c.preview.content).slice(0, 500)}
                        {String(c.preview.content).length > 500 ? '…' : ''}
                      </div>
                    ) : null}
                  </div>

                  <div className="flex gap-2">
                    <KianaButton
                      variant="secondary"
                      disabled={!cid || busyId === cid || c?.status !== 'pending'}
                      onClick={() => cid && decide(cid, 'deny')}
                    >
                      Ablehnen
                    </KianaButton>
                    <KianaButton
                      variant="primary"
                      disabled={!cid || busyId === cid || c?.status !== 'pending'}
                      onClick={() => cid && decide(cid, 'accept')}
                    >
                      Annehmen
                    </KianaButton>
                  </div>
                </div>
              </KianaCard>
            )
          })}
        </div>
      )}
    </div>
  )
}
