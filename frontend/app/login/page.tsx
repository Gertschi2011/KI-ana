'use client'
import { useState } from 'react'

export default function LoginPage(){
  const [email, setEmail] = useState('admin@example.com')
  const [password, setPassword] = useState('admin123')
  const [msg, setMsg] = useState('')

  async function onSubmit(e: React.FormEvent){
    e.preventDefault()
    setMsg('')
    try{
      const r = await fetch(process.env.NEXT_PUBLIC_API_BASE + '/api/auth/login', {method:'POST', headers:{'Content-Type':'application/json'}, body: JSON.stringify({email, password})})
      const j = await r.json()
      if(!r.ok || !j.ok){ setMsg('Login fehlgeschlagen'); return }
      localStorage.setItem('access', j.access)
      setMsg('Login ok')
    }catch(err:any){ setMsg('Fehler: ' + String(err)) }
  }

  return (
    <div>
      <h1>Login</h1>
      <form onSubmit={onSubmit} style={{display:'grid', gap:8, maxWidth:320}}>
        <input value={email} onChange={e=>setEmail(e.target.value)} placeholder='E-Mail' />
        <input value={password} onChange={e=>setPassword(e.target.value)} type='password' placeholder='Passwort' />
        <button type='submit'>Anmelden</button>
        <div>{msg}</div>
      </form>
    </div>
  )
}
