'use client'
import { useEffect, useState } from 'react'
import { login, getMe } from '../../../lib/api'

export default function LoginPage(){
  const [username, setUsername] = useState('')
  const [password, setPassword] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

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
      <div className="card">
        <div className="text-lg font-semibold">Login</div>
        <div className="small mt-1">Melde dich an, um Chat und Papa zu nutzen.</div>
      </div>

      <div className="card">
      <form className="form" onSubmit={onSubmit}>
        <label>
          <div className="small">Benutzername oder E-Mail</div>
          <input className="input" value={username} onChange={e=>setUsername(e.target.value)} required />
        </label>
        <label>
          <div className="small">Passwort</div>
          <input className="input" type="password" value={password} onChange={e=>setPassword(e.target.value)} required />
        </label>
        <button className="kiana-btn kiana-btn-primary" disabled={busy} type="submit">{busy ? 'Anmelden …' : 'Anmelden'}</button>
      </form>
      {msg && <div className="mt-3 kiana-alert kiana-alert-error">{msg}</div>}
      </div>
    </div>
  )
}
