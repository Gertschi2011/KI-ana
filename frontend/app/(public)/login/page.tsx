'use client'
import { useEffect, useState } from 'react'
import { login, getMe } from '../../../lib/api'
import Link from 'next/link'
import KianaCard from '../../../components/ui/KianaCard'
import KianaButton from '../../../components/ui/KianaButton'

export default function LoginPage(){
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  const canSubmit = username.trim().length > 0 && password.length > 0

  // If already authenticated, go to chat directly
  useEffect(()=>{
    (async()=>{
      try{
        const me = await getMe()
        if(me?.auth) {
          window.location.replace('/app/chat')
        }
      }catch{}
    })()
  },[])

  async function onSubmit(e: React.FormEvent){
    e.preventDefault()
    setMsg(''); setBusy(true)
    try{
      await login({ username, password, remember: true })

      // Validate session via /api/me then redirect
      const me = await getMe()
      if(me?.auth){
        try {
          const u = (me as any)?.user?.username || username
          if(u) localStorage.setItem('kiana_username', String(u))
        } catch {}
        window.location.replace('/app/chat')
        return
      }

      setMsg('Login fehlgeschlagen (keine Session)')
    }catch(err:any){
      const text = typeof err?.message === 'string' ? err.message : ''
      setMsg(text || 'Login fehlgeschlagen')
    }finally{ setBusy(false) }
  }

  return (
    <div className="max-w-md mx-auto grid gap-4">
      <KianaCard>
        <div className="text-lg font-semibold">Willkommen zurück 👋</div>
        <div className="small mt-1">Schön, dass du wieder da bist. Wir gehen direkt in den Chat.</div>
      </KianaCard>

      <KianaCard>
        <form className="form" onSubmit={onSubmit}>
          <label>
            <div className="small">Benutzername oder E-Mail</div>
            <input className="input" value={username} onChange={e=>setUsername(e.target.value)} required />
            <div className="small mt-1" style={{ opacity: 0.75 }}>
              Kein Stress. Du darfst hier einfach du sein.
            </div>
          </label>
          <label>
            <div className="small">Passwort</div>
            <input className="input" type="password" value={password} onChange={e=>setPassword(e.target.value)} required />
            <div className="small mt-1" style={{ opacity: 0.75 }}>
              Deine Daten gehören dir. Wir sind leise. Kein Spam.
            </div>
          </label>
          <KianaButton variant="primary" disabled={busy || !canSubmit} type="submit">
            {busy ? 'Anmelden …' : 'Anmelden'}
          </KianaButton>
        </form>

        {msg && <div className="mt-3 kiana-alert kiana-alert-error"><div className="small">{msg}</div></div>}

        <div className="small mt-4" style={{opacity:0.8}}>
          Noch kein Konto? <Link className="underline" href="/register">Kostenlos starten</Link>
        </div>
      </KianaCard>
    </div>
  )
}
