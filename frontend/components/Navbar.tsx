'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import { getMe, logout } from '../lib/api'

export default function Navbar(){
  const [name, setName] = useState<string>('Gast')
  const [isAuthed, setIsAuthed] = useState<boolean>(false)
  const [roles, setRoles] = useState<string[]>([])
  const [role, setRole] = useState<string>('')
  const [flags, setFlags] = useState<{ is_admin?: boolean; is_creator?: boolean; is_papa?: boolean }>({})
  const [caps, setCaps] = useState<Record<string, any>>({})
  const pathname = usePathname() || ''
  const buildSha = (process.env.NEXT_PUBLIC_BUILD_SHA || 'unknown').slice(0, 12)

  useEffect(()=>{
    let mounted = true
    ;(async()=>{
      try{
        const me:any = await getMe()
        if(mounted){
          const authed = !!me?.auth
          setIsAuthed(authed)
          const u = authed ? (me?.user || null) : null
          const n = u?.username || u?.email || 'Gast'
          setName(String(n || 'Gast'))
          const rolesRaw = Array.isArray(u?.roles) ? u.roles : []
          setRoles(rolesRaw.map((r: any) => String(r).toLowerCase()))
          setRole(String(u?.role || '').toLowerCase())
          setFlags({
            is_admin: !!u?.is_admin,
            is_creator: !!u?.is_creator,
            is_papa: !!u?.is_papa,
          })
          const capsObj = (me?.caps && typeof me.caps === 'object') ? me.caps : ((u?.caps && typeof u.caps === 'object') ? u.caps : {})
          setCaps(capsObj || {})
        }
      }catch{}
    })()
    return ()=>{ mounted = false }
  },[])

  async function onLogout(){
    try{ await logout() }catch{}
    try{ localStorage.clear() }catch{}
    window.location.href = '/login'
  }

  const isAdmin = !!flags.is_admin || roles.includes('admin') || role === 'admin'
  const isCreator = !!flags.is_creator || roles.includes('creator') || role === 'creator'
  const isPapa = !!flags.is_papa || roles.includes('papa') || role === 'papa'
  const canSeeAdmin = isAdmin || isCreator
  const canViewBlockViewer = !!(caps?.can_view_block_viewer)
  const showBuild = canSeeAdmin

  const isActive = (href: string) => {
    if (href === '/app/dashboard') return pathname === '/app/dashboard'
    if (pathname === href) return true
    return pathname.startsWith(href + '/')
  }

  const authedTabs: Array<{ href: string; label: string; show?: boolean; external?: boolean }> = [
    { href: '/app/dashboard', label: '🏠 Dashboard', show: true },
    { href: '/app/chat', label: '💬 Chat', show: true },
    { href: '/app/papa', label: '👨‍👧 Papa', show: isPapa },
    { href: '/app/settings', label: '⚙️ Einstellungen', show: true },
    { href: '/app/admin/timeflow', label: '⏱️ TimeFlow', show: canSeeAdmin },
    { href: '/app/monitoring', label: '📈 Monitoring', show: canSeeAdmin },
    { href: '/app/tools', label: '🧰 Tools', show: canSeeAdmin },
    { href: '/app/blockviewer', label: '🧱 Block Viewer', show: canViewBlockViewer },
    { href: '/app/admin/users', label: '👥 Benutzer', show: canSeeAdmin },
  ]

  const publicTabs: Array<{ href: string; label: string }> = [
    { href: '/', label: 'Start' },
    { href: '/login', label: 'Login' },
    { href: '/register', label: 'Registrieren' },
  ]

  return (
    <header className="kiana-header">
      <div className="kiana-header-inner">
        <div className="kiana-header-row">
          <div>
            <div className="kiana-brand-title" style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <img
                src="/static/Avatar_KI_ana.png"
                alt="Kiana"
                width={42}
                height={42}
                style={{ borderRadius: 999, border: '2px solid rgba(255,255,255,0.22)', background: 'rgba(255,255,255,0.10)' }}
              />
              <span>KI_ana</span>
            </div>
            <div className="kiana-brand-sub">Online</div>
          </div>

          <div className="kiana-header-actions">
            <div className="kiana-status">
              <div className="kiana-status-label">Status</div>
              <div className="kiana-status-line">
                <span className="kiana-header-status-dot" aria-hidden />
                <span className="kiana-status-text">Online</span>
              </div>
              {showBuild && (
                <div className="kiana-status-label" style={{ marginTop: 4, opacity: 0.9 }}>Build {buildSha}</div>
              )}
            </div>
            {isAuthed && (
              <>
                <div className="kiana-userpill">👤 {name}{isCreator ? ' (Creator)' : isAdmin ? ' (Admin)' : isPapa ? ' (Papa)' : ''}</div>
                <button className="kiana-header-btn" onClick={onLogout}>Logout</button>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="kiana-navtabs">
        <div className="kiana-navtabs-inner">
          <nav className="kiana-navtabs-list" aria-label="Navigation">
            {(isAuthed ? authedTabs : publicTabs)
              .filter((t: any) => t.show !== false)
              .map((t: any) => (
                <Link
                  key={t.href}
                  href={t.href}
                  className={`kiana-tab ${isActive(t.href) ? 'kiana-tab-active' : ''}`}
                >
                  {t.label}
                </Link>
              ))}
          </nav>
        </div>
      </div>
    </header>
  )
}
