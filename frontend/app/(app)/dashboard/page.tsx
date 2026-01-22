'use client'

import Link from 'next/link'
import { useEffect, useMemo, useState } from 'react'

export default function AppDashboardPage(){
  const [me, setMe] = useState<any>(null)
  const [loading, setLoading] = useState(true)

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

  const u = me?.auth ? me?.user : null
  const role = String(u?.role ?? '').toLowerCase()
  const roles = Array.isArray(u?.roles) ? u.roles.map((x:any)=>String(x).toLowerCase()) : []
  const isAdmin = !!u?.is_admin || roles.includes('admin') || role === 'admin'
  const isCreator = !!u?.is_creator || roles.includes('creator') || role === 'creator'
  const isPapa = !!u?.is_papa || roles.includes('papa') || role === 'papa'
  const canSeeAdmin = isAdmin || isCreator

  const cards = useMemo(()=>{
    const items: Array<{ title: string; desc: string; href: string; show?: boolean }> = [
      { title: '💬 Chat', desc: 'Mit KI_ana chatten (Streaming).', href: '/app/chat', show: true },
      { title: '👨‍👧 Papa', desc: 'Papa-Modus & Inhalte.', href: '/app/papa', show: isPapa },
      { title: '⚙️ Einstellungen', desc: 'Profil- und App-Einstellungen.', href: '/app/settings', show: true },
      { title: '⏱️ TimeFlow', desc: 'TimeFlow Status & Konfiguration.', href: '/app/admin/timeflow', show: canSeeAdmin },
      { title: '📈 Monitoring', desc: 'Grafana/Prometheus Links.', href: '/app/monitoring', show: canSeeAdmin },
      { title: '🧰 Tools', desc: 'Tools & Viewer.', href: '/app/tools', show: canSeeAdmin },
      { title: '👥 Benutzer', desc: 'Benutzermanagement.', href: '/app/admin/users', show: canSeeAdmin },
    ]
    return items.filter(i=>i.show !== false)
  }, [isPapa, canSeeAdmin])

  return (
    <div className="grid gap-4">
      <div className="card">
        <div className="text-lg font-semibold">Dashboard</div>
        <div className="small mt-1">Übersicht & Schnellzugriff auf KI_ana.</div>
        {loading ? <div className="small mt-3">Lade…</div> : null}
      </div>

      <div className="grid md:grid-cols-2 gap-4">
        {cards.map((c)=> (
          <Link key={c.href} href={c.href} className="card" style={{ display: 'block' }}>
            <div className="text-base font-semibold">{c.title}</div>
            <div className="small mt-1">{c.desc}</div>
          </Link>
        ))}
      </div>
    </div>
  )
}
