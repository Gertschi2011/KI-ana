'use client'

import { useEffect, useState } from 'react'
import KianaCard from '../../../components/ui/KianaCard'
import KianaButton from '../../../components/ui/KianaButton'

export default function BlockViewerPage(){
  const [access, setAccess] = useState<'loading' | 'denied' | 'allowed'>('loading')

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
      <div className="max-w-6xl mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">Block Viewer</div>
          <div className="small mt-1">Prüfe Zugriff…</div>
        </KianaCard>
      </div>
    )
  }

  if (access === 'denied') {
    return (
      <div className="max-w-6xl mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">Block Viewer</div>
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
    <div className="max-w-6xl mx-auto grid gap-4">
      <KianaCard>
        <div className="text-lg font-semibold">Block Viewer</div>
        <div className="small mt-1">Der Viewer läuft eingebettet (ohne Legacy‑Navbar).</div>
      </KianaCard>

      <KianaCard hover={false} reveal={false} className="p-0 overflow-hidden">
        <iframe
          title="Block Viewer"
          src="/static/block_viewer.html?embed=1"
          style={{ width: '100%', height: '75vh', border: 0, background: 'white' }}
        />
      </KianaCard>
    </div>
  )
}
