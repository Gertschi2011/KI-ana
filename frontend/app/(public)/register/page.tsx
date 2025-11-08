'use client'
import { useState } from 'react'

export default function RegisterPage(){
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  async function onSubmit(e: React.FormEvent){
    e.preventDefault()
    setMsg(''); setBusy(true)
    try{
      const res = await fetch('/api/register', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username, email, password })
      })
      if(!res.ok){
        const txt = await res.text().catch(()=> '')
        throw new Error(txt || 'Registrierung fehlgeschlagen')
      }
      setMsg('Erfolgreich registriert. Weiterleitung …')
      setTimeout(()=>{ window.location.href = '/login' }, 800)
    }catch(err:any){ setMsg(err?.message || 'Registrierung fehlgeschlagen') }
    finally{ setBusy(false) }
  }

  return (
    <div className="max-w-md mx-auto p-6">
      <h1 className="text-2xl font-bold mb-4">Registrieren</h1>
      <form className="form" onSubmit={onSubmit}>
        <label>
          <div className="small">Benutzername</div>
          <input className="input" value={username} onChange={e=>setUsername(e.target.value)} required />
        </label>
        <label>
          <div className="small">E-Mail</div>
          <input className="input" type="email" value={email} onChange={e=>setEmail(e.target.value)} required />
        </label>
        <label>
          <div className="small">Passwort</div>
          <input className="input" type="password" value={password} onChange={e=>setPassword(e.target.value)} required />
        </label>
        <button className="btn-light" disabled={busy} type="submit">Konto erstellen</button>
      </form>
      {msg && <div className="mt-3">{msg}</div>}
    </div>
  )
}
