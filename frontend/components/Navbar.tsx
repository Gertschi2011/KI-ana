'use client'
import Link from 'next/link'
import { useEffect, useState } from 'react'
import { getMe, logout } from '../lib/api'

type Props = { variant?: 'light' | 'dark' }

export default function Navbar({ variant = 'dark' }: Props){
  const [name, setName] = useState<string>('Gast')
  const [roles, setRoles] = useState<string[]>([])
  const isAdmin = roles?.includes('admin') || roles?.includes('creator')

  useEffect(()=>{
    let mounted = true
    ;(async()=>{
      try{
        const me:any = await getMe()
        const n = me?.user?.username || me?.user?.email || 'Gast'
        if(mounted){
          setName(n)
          setRoles(Array.isArray(me?.user?.roles)? me.user.roles : [])
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

  const isLight = variant === 'light'
  const navClass = `nav ${isLight? 'nav-light' : 'nav-dark'}`
  const btnClass = isLight? 'btn-light' : 'btn-dark'

  return (
    <header className={navClass}>
      <div className="nav-inner">
        <Link href="/" className="brand">KI_ana</Link>
        {isLight ? (
          <>
            <Link href="/">Start</Link>
            <Link href="/skills">Fähigkeiten</Link>
            <Link href="/pricing">Preise</Link>
            <Link href="/login">Login</Link>
            <Link href="/register">Registrieren</Link>
            <div className="spacer" />
          </>
        ) : (
          <>
            <Link href="/chat">Chat</Link>
            <Link href="/papa">Papa</Link>
            <Link href="/settings">Einstellungen</Link>
            <div className="spacer" />
            <div className="mr-2">👤 {name}</div>
            {isAdmin && (
              <Link href="/admin/users" className="mr-2">Admin</Link>
            )}
            <button className={btnClass} onClick={onLogout}>Logout</button>
          </>
        )}
      </div>
    </header>
  )
}
