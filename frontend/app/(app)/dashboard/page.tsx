'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'

export default function AppDashboardPage(){
  const [me, setMe] = useState<any>(null)
  const [loading, setLoading] = useState(true)
  const [goals, setGoals] = useState<any[] | null>(null)
  const [reflect, setReflect] = useState<any | null>(null)
  const [lastTopic, setLastTopic] = useState<string>('')
  const [busy, setBusy] = useState(false)

  useEffect(()=>{
    let mounted = true
    ;(async()=>{
      try{
        const r = await fetch('/api/me', { credentials: 'include' })
        const j = await r.json().catch(()=>({} as any))
        if(mounted) setMe(j)
      }catch{
        if(mounted) setMe(null)
      }finally{
        if(mounted) setLoading(false)
      }
    })()
    return ()=>{ mounted = false }
  },[])

  useEffect(() => {
    let mounted = true
    ;(async () => {
      try {
        const rg = await fetch('/api/goals', { credentials: 'include' })
        const jg = await rg.json().catch(() => ({} as any))
        const items = Array.isArray(jg?.items) ? jg.items : []
        if (mounted) setGoals(items)
      } catch {
        if (mounted) setGoals([])
      }

      try {
        const rr = await fetch('/api/reflection/auto/stats', { credentials: 'include' })
        const jr = await rr.json().catch(() => ({} as any))
        if (mounted) setReflect(jr?.stats ?? null)
      } catch {
        if (mounted) setReflect(null)
      }

      try {
        const rs = await fetch('/api/chat/conv_state', { credentials: 'include' })
        const js = await rs.json().catch(() => ({} as any))
        const lt = typeof js?.last_topic === 'string' ? js.last_topic : ''
        if (mounted) setLastTopic((lt || '').trim())
      } catch {
        if (mounted) setLastTopic('')
      }
    })()
    return () => { mounted = false }
  }, [])

  const u = me?.auth ? me?.user : null
  const role = String(u?.role ?? '').toLowerCase()
  const roles = Array.isArray(u?.roles) ? u.roles.map((x:any)=>String(x).toLowerCase()) : []
  const isAdmin = !!u?.is_admin || roles.includes('admin') || role === 'admin'
  const isCreator = !!u?.is_creator || roles.includes('creator') || role === 'creator'
  const isPapa = !!u?.is_papa || roles.includes('papa') || role === 'papa'
  const canSeeAdmin = isAdmin || isCreator
  const canSeePapaTools = isCreator

  const topGoal = Array.isArray(goals) && goals.length > 0 ? goals[0] : null
  const goalTopic = String(topGoal?.topic || '').trim()
  const goalBlocks = Number(topGoal?.progress?.blocks ?? 0)

  const displayName = String(u?.name || u?.username || u?.email || '').trim() || 'du'
  const greeting = (() => {
    try {
      const h = new Date().getHours()
      if (h < 5) return 'Gute Nacht'
      if (h < 11) return 'Guten Morgen'
      if (h < 17) return 'Guten Tag'
      if (h < 22) return 'Guten Abend'
      return 'Gute Nacht'
    } catch {
      return 'Hallo'
    }
  })()

  async function proposeGoal() {
    setBusy(true)
    try {
      await fetch('/api/goals/propose', { credentials: 'include' })
    } catch {
      // ignore
    }
    try {
      const rg = await fetch('/api/goals', { credentials: 'include' })
      const jg = await rg.json().catch(() => ({} as any))
      const items = Array.isArray(jg?.items) ? jg.items : []
      setGoals(items)
    } catch {
      // ignore
    } finally {
      setBusy(false)
    }
  }

  const baseCards = useMemo(() => {
    const items: Array<{ title: string; desc: string; href: string; show?: boolean }> = [
      { title: '💬 Chat', desc: 'Einfach losreden – KI_ana hört zu.', href: '/app/chat', show: true },
      { title: '⚙️ Einstellungen', desc: 'Dein Profil und dein Stil.', href: '/app/settings', show: true },
      { title: '👨‍👧 Papa Tools', desc: 'Nur für Gerald: behutsam lernen, bewusst entscheiden.', href: '/app/papa', show: canSeePapaTools },
    ]
    return items.filter((i) => i.show !== false)
  }, [canSeePapaTools])

  const workshopCards = useMemo(() => {
    if (!canSeeAdmin) return [] as Array<{ title: string; desc: string; href: string }>
    return [
      { title: '🧱 Block Viewer', desc: 'Wissensblöcke ansehen.', href: '/app/blockviewer' },
      { title: '👥 Benutzerverwaltung', desc: 'Accounts & Rollen.', href: '/app/admin/users' },
      { title: '⏱️ Timeflow', desc: 'Status & Konfiguration.', href: '/app/admin/timeflow' },
      { title: '📈 Monitoring', desc: 'Qualitätsübersicht.', href: '/app/monitoring' },
      { title: '🧰 Tools', desc: 'Interne Werkzeuge.', href: '/app/tools' },
    ]
  }, [canSeeAdmin])

  return (
    <div className="grid gap-4">
      <div className="card">
        <div className="text-lg font-semibold">{greeting}, {displayName} 👋</div>
        <div className="small mt-1">Schön, dass du da bist. Hier ist dein ruhiger Überblick – ohne Druck, ohne Lärm.</div>
        <div className="small mt-2" style={{ opacity: 0.85 }}>
          Dieses Dashboard hilft dir, wieder reinzufinden: Was war zuletzt wichtig – und was lohnt sich als nächstes?
        </div>
        {loading ? <div className="small mt-3">Ich sammle kurz alles ein…</div> : null}
      </div>

      <div className="grid md:grid-cols-3 gap-4">
        <div className="card">
          <div className="text-base font-semibold">🫧 Status</div>
          <div className="small mt-2">Ich lerne gerade…</div>
          <div className="mt-1 font-semibold">
            {goalTopic ? `„${goalTopic}“` : '…deinen Stil und deine Prioritäten.'}
          </div>
          <div className="small mt-2">Letzte Erinnerung:</div>
          <div className="small mt-1">
            {lastTopic ? `„${lastTopic}“` : 'Hier warten neue Gedanken auf dich ✨'}
          </div>
        </div>

        <div className="card">
          <div className="text-base font-semibold">⚡ Quick Actions</div>
          <div className="mt-3 grid gap-2">
            <Link className="kiana-header-btn" href="/app/chat">💬 Chat starten</Link>
            {canSeePapaTools ? (
              <Link className="kiana-header-btn" href="/app/papa/learning">🧠 Lernentscheidungen</Link>
            ) : null}
            <Link className="kiana-header-btn" href="/app/settings">⚙️ Einstellungen</Link>
          </div>
        </div>

        <div className="card">
          <div className="text-base font-semibold">🕒 Rhythmus</div>
          {reflect ? (
            <>
              <div className="small mt-2">Antworten seit letzter Reflexion: {Number(reflect?.answer_count ?? 0) || 0}</div>
              <div className="small mt-1">Nächste Reflexion in: {Number(reflect?.next_reflection_in ?? 0) || 0}</div>
              <div className="small mt-1">Reflexionen gesamt: {Number(reflect?.total_reflections ?? 0) || 0}</div>
            </>
          ) : (
            <div className="small mt-2">Noch keine Rhythmus‑Daten sichtbar.</div>
          )}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        <div className="card">
          <div className="text-base font-semibold">🎯 Lernziel</div>
          {goals === null ? (
            <div className="small mt-2">Ich schaue kurz nach…</div>
          ) : goalTopic ? (
            <>
              <div className="small mt-2">Aktuell:</div>
              <div className="mt-1 font-semibold">{goalTopic}</div>
              <div className="small mt-2">Wissensblöcke zum Thema: {Number.isFinite(goalBlocks) ? goalBlocks : 0}</div>
            </>
          ) : (
            <>
              <div className="small mt-2">Hier ist noch Platz für ein erstes Lernziel ✨</div>
              <div className="mt-4 flex gap-2 flex-wrap">
                <button className="kiana-header-btn" onClick={proposeGoal} disabled={busy}>
                  Vorschlag erstellen
                </button>
                <Link className="kiana-header-btn" href="/app/settings">Einrichten</Link>
              </div>
            </>
          )}
        </div>

        <div className="card">
          <div className="text-base font-semibold">📊 Fortschritt</div>
          {goals === null ? (
            <div className="small mt-2">Ich sortiere das gerade…</div>
          ) : goalTopic ? (
            <>
              <div className="small mt-2">Du baust gerade Wissen zu „{goalTopic}“ auf.</div>
              <div className="mt-3">
                <div className="small">Blöcke: {Number.isFinite(goalBlocks) ? goalBlocks : 0}</div>
                <div className="kiana-progress mt-2">
                  <div className="kiana-progress-bar" style={{ width: `${Math.min(100, Math.max(8, (Number.isFinite(goalBlocks) ? goalBlocks : 0) * 10))}%` }} />
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="small mt-2">Hier wartet dein erster Schritt ✨</div>
              <div className="mt-4">
                <Link className="kiana-header-btn" href="/app/settings">Einrichten</Link>
              </div>
            </>
          )}
        </div>
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {baseCards.map((c)=> (
          <Link key={c.href} href={c.href} className="card" style={{ display: 'block' }}>
            <div className="text-base font-semibold">{c.title}</div>
            <div className="small mt-1">{c.desc}</div>
          </Link>
        ))}
      </div>

      {workshopCards.length > 0 ? (
        <div className="grid gap-3">
          <div className="small" style={{ opacity: 0.8 }}>Werkstatt (nur intern)</div>
          <div className="grid md:grid-cols-2 gap-4">
            {workshopCards.map((c) => (
              <Link key={c.href} href={c.href} className="card" style={{ display: 'block' }}>
                <div className="text-base font-semibold">{c.title}</div>
                <div className="small mt-1">{c.desc}</div>
              </Link>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
