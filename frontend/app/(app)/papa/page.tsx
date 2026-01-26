'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import KianaCard from '../../../components/ui/KianaCard'
import KianaButton from '../../../components/ui/KianaButton'

export default function PapaPage(){
  const [access, setAccess] = useState<'loading' | 'denied' | 'allowed'>('loading')
  const [learningCounts, setLearningCounts] = useState<{ pending: number; accepted: number; denied: number; total: number } | null>(null)
  const [learningRecent, setLearningRecent] = useState<Array<{ status: string; topic: string; created_at?: number }> | null>(null)
  const [decisions24h, setDecisions24h] = useState<number | null>(null)

  function fmtTs(ts?: number) {
    if (!ts || typeof ts !== 'number') return ''
    try {
      return new Date(ts * 1000).toLocaleString()
    } catch {
      return ''
    }
  }

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
        const allowed = Boolean(isCreator)
        if (!mounted) return
        setAccess(allowed ? 'allowed' : 'denied')
      } catch {
        if (!mounted) return
        setAccess('denied')
      }
    })()
    return () => { mounted = false }
  }, [])

  useEffect(() => {
    if (access !== 'allowed') return
    let mounted = true
    ;(async () => {
      try {
        const r = await fetch('/api/v2/learning/candidates?status=all&limit=200', { credentials: 'include' })
        const j = await r.json().catch(() => ({} as any))
        const items = Array.isArray(j?.items) ? j.items : []
        const counts = { pending: 0, accepted: 0, denied: 0, total: items.length }
        const now = Date.now()
        let d24 = 0
        const recent: Array<{ status: string; topic: string; created_at?: number }> = []
        for (const it of items) {
          const st = String(it?.status || '').toLowerCase()
          if (st === 'pending') counts.pending += 1
          else if (st === 'accepted') counts.accepted += 1
          else if (st === 'denied') counts.denied += 1
          const ts = typeof it?.created_at === 'number' ? it.created_at : undefined
          if ((st === 'accepted' || st === 'denied') && ts) {
            const ageMs = now - ts * 1000
            if (ageMs >= 0 && ageMs <= 24 * 3600 * 1000) d24 += 1
          }
          if ((st === 'accepted' || st === 'denied') && recent.length < 6) {
            recent.push({ status: st, topic: String(it?.topic || 'Ohne Topic'), created_at: ts })
          }
        }
        // Sort recent by created_at desc (best-effort)
        recent.sort((a, b) => Number(b.created_at || 0) - Number(a.created_at || 0))
        if (mounted) {
          setLearningCounts(counts)
          setDecisions24h(d24)
          setLearningRecent(recent.slice(0, 5))
        }
      } catch {
        if (mounted) {
          setLearningCounts(null)
          setLearningRecent(null)
          setDecisions24h(null)
        }
      }
    })()
    return () => { mounted = false }
  }, [access])

  if (access === 'loading') {
    return (
      <div className="max-w-5xl mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">Papa Tools</div>
          <div className="small mt-1">Prüfe Zugriff…</div>
        </KianaCard>
      </div>
    )
  }

  if (access === 'denied') {
    return (
      <div className="max-w-5xl mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">Papa Tools</div>
          <div className="small mt-1">Kein Zugriff. Dieser Bereich ist nur für Gerald (Creator) sichtbar.</div>
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
            <div className="text-lg font-semibold">Papa Tools</div>
            <div className="small mt-1">Hier begleitest du KI_anas Lernen – behutsam, nachvollziehbar, mit gutem Gefühl.</div>
          </div>
          <Link href="/app/chat">
            <KianaButton variant="primary">Zum Chat</KianaButton>
          </Link>
        </div>

        <div className="kiana-inset mt-5">
          <div className="font-semibold">Kurzstatus</div>
          <div className="small mt-1">
            {learningCounts
              ? `Entscheidungen: ${learningCounts.pending} offen · ${learningCounts.accepted} angenommen · ${learningCounts.denied} verworfen`
              : 'Hier warten neue Gedanken auf dich ✨'}
          </div>
          <div className="small mt-1">
            {typeof decisions24h === 'number'
              ? `Heute (24h): ${decisions24h} Entscheidungen`
              : 'Heute (24h): noch keine Daten sichtbar.'}
          </div>

          <div className="mt-4">
            <div className="font-semibold">Letzte Entscheidungen</div>
            {learningRecent && learningRecent.length > 0 ? (
              <div className="mt-2 grid gap-1">
                {learningRecent.map((x, idx) => (
                  <div key={idx} className="small">
                    <span style={{ fontWeight: 700 }}>{x.status === 'accepted' ? '✓ angenommen' : '✕ abgelehnt'}</span>
                    {' · '}{x.topic}
                    {x.created_at ? <span style={{ color: 'rgba(17,24,39,0.60)' }}> · {fmtTs(x.created_at)}</span> : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="small mt-2">Noch keine Entscheidungen sichtbar – das ist okay. Erstmal ankommen.</div>
            )}
          </div>
        </div>
      </KianaCard>

      <KianaCard>
        <div className="text-base font-semibold">Warum fragt KI_ana manchmal nach?</div>
        <div className="small mt-2">
          Weil gutes Lernen Zustimmung braucht. Wenn etwas „wie Wissen“ klingt, aber noch unscharf ist, fragt KI_ana kurz nach.
          Nicht um zu nerven – sondern um sauber zu lernen.
        </div>
        <div className="small mt-3">
          Du schützt die Qualität: <span style={{ fontWeight: 700 }}>annehmen</span> (es darf bleiben) oder
          <span style={{ fontWeight: 700 }}> verwerfen</span> (es war nur ein Moment).
        </div>
      </KianaCard>

      <div className="grid md:grid-cols-2 gap-4">
        <Link href="/app/papa/learning" className="card" style={{ display: 'block' }}>
          <div className="font-semibold">🧠 Lernentscheidungen</div>
          <div className="small mt-1">
            {learningCounts
              ? `${learningCounts.pending} offen – in Ruhe „Ja“ oder „Nein“ sagen.`
              : 'Hier warten neue Gedanken auf dich ✨'}
          </div>
        </Link>

        <div className="card" style={{ display: 'block' }}>
          <div className="font-semibold">🛡️ Qualität & Schutz</div>
          <div className="small mt-1">
            KI_ana lernt nicht heimlich. Du schützt, was nur ein Moment war – und lässt bleiben, was wirklich wichtig ist.
          </div>
        </div>

        <div className="card" style={{ display: 'block' }}>
          <div className="font-semibold">🔎 Explain & Transparenz</div>
          <div className="small mt-1">
            Im Chat siehst du (nur als Creator) ein kleines „ⓘ“ bei Antworten. Dort erklärt KI_ana sanft, worauf sie sich gestützt hat.
          </div>
        </div>

        <Link href="/app/chat" className="card" style={{ display: 'block' }}>
          <div className="font-semibold">💬 Zurück in den Chat</div>
          <div className="small mt-1">Weil Lernen am besten im Gespräch passiert.</div>
        </Link>
      </div>
    </div>
  )
}
