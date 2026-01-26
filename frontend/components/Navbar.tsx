'use client'
import Link from 'next/link'
import { usePathname } from 'next/navigation'
import { useEffect, useState } from 'react'
import { getMe, logout } from '../lib/api'
import { LayoutGroup, motion } from 'framer-motion'
import { kianaTransitionMedium } from './ui/motionTokens'

export default function Navbar(){
  const [name, setName] = useState<string>('Gast')
  const [isAuthed, setIsAuthed] = useState<boolean>(false)
  const [roles, setRoles] = useState<string[]>([])
  const [role, setRole] = useState<string>('')
  const [flags, setFlags] = useState<{ is_admin?: boolean; is_creator?: boolean; is_papa?: boolean }>({})
  const [caps, setCaps] = useState<Record<string, any>>({})
  const pathname = usePathname() || ''
  const buildSha = (process.env.NEXT_PUBLIC_BUILD_SHA || 'unknown').slice(0, 12)
  // Phase 2 visibility rule: build/debug markers never for normal users.

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
  const canSeeCreatorNav = isAdmin || isCreator
  const showBuild = canSeeCreatorNav

  const brandHref = isAuthed ? '/app/chat' : '/'

  const isActive = (href: string) => {
    if (href === '/app/dashboard') return pathname === '/app/dashboard'
    if (pathname === href) return true
    return pathname.startsWith(href + '/')
  }

  const authedTabs: Array<{ href: string; label: string; show?: boolean; external?: boolean }> = [
    { href: '/app/dashboard', label: 'Dashboard', show: true },
    { href: '/app/chat', label: 'Chat', show: true },
    { href: '/app/settings', label: 'Einstellungen', show: true },
    { href: '/app/papa', label: 'Papa Tools', show: isCreator },
    { href: '/app/admin/users', label: 'Benutzerverwaltung', show: canSeeCreatorNav },
    { href: '/app/blockviewer', label: 'Block Viewer', show: canSeeCreatorNav },
    { href: '/app/admin/timeflow', label: 'Timeflow', show: canSeeCreatorNav },
  ]

  const publicTabs: Array<{ href: string; label: string }> = [
    { href: '/', label: 'Home' },
    { href: '/pakete', label: 'Pakete' },
    { href: '/login', label: 'Login' },
  ]

  return (
    <header className="kiana-header">
      <div className="kiana-header-inner">
        <div className="kiana-header-row">
          <div>
            <Link className="kiana-brand-link" href={brandHref} aria-label="KI_ana Home">
              <span className="kiana-brand-mark" aria-hidden />
              <div>
                <div className="kiana-brand-title">KI_ana</div>
                <div className="kiana-brand-sub">verspielt • lernend • ruhig</div>
              </div>
            </Link>
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
            {!isAuthed && (
              <div className="flex items-center gap-2">
                <Link className="kiana-header-btn" href="/login">Login</Link>
                <Link className="kiana-header-btn" href="/register">Registrieren</Link>
              </div>
            )}
            {isAuthed && (
              <>
                <div className="kiana-userpill">{name}{isCreator ? ' (Creator)' : isAdmin ? ' (Admin)' : isPapa ? ' (Papa)' : ''}</div>
                <button className="kiana-header-btn" onClick={onLogout}>Logout</button>
              </>
            )}
          </div>
        </div>
      </div>

      <div className="kiana-navtabs">
        <div className="kiana-navtabs-inner">
          <LayoutGroup>
            <nav className="kiana-navtabs-list" aria-label="Navigation">
              {(isAuthed ? authedTabs : publicTabs)
                .filter((t: any) => t.show !== false)
                .map((t: any) => {
                  const active = isActive(t.href)
                  const isHash = typeof t.href === 'string' && t.href.includes('#')
                  return (
                    isHash ? (
                      <a
                        key={t.href}
                        href={t.href}
                        className={`kiana-tab ${active ? 'kiana-tab-active' : ''}`}
                      >
                        {active ? (
                          <motion.span
                            layoutId="kiana-nav-pill"
                            className="kiana-tab-active-pill"
                            transition={kianaTransitionMedium()}
                          />
                        ) : null}
                        <span style={{ position: 'relative', zIndex: 1 }}>{t.label}</span>
                      </a>
                    ) : (
                      <Link
                        key={t.href}
                        href={t.href}
                        scroll={true}
                        className={`kiana-tab ${active ? 'kiana-tab-active' : ''}`}
                      >
                        {active ? (
                          <motion.span
                            layoutId="kiana-nav-pill"
                            className="kiana-tab-active-pill"
                            transition={kianaTransitionMedium()}
                          />
                        ) : null}
                        <span style={{ position: 'relative', zIndex: 1 }}>{t.label}</span>
                      </Link>
                    )
                  )
                })}
            </nav>
          </LayoutGroup>
        </div>
      </div>
    </header>
  )
}
