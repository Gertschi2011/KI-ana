'use client'
import { useEffect, useMemo, useState } from 'react'
import { getMe } from '../../../lib/api'
import Link from 'next/link'
import KianaCard from '../../../components/ui/KianaCard'
import KianaButton from '../../../components/ui/KianaButton'

export default function RegisterPage(){
  const MIN_PW = Number((process.env.NEXT_PUBLIC_MIN_PASSWORD_LEN as any) ?? 10) || 10

  const [name, setName] = useState('')
  const [username, setUsername] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [password2, setPassword2] = useState('')

  const [msg, setMsg] = useState('')
  const [msgKind, setMsgKind] = useState<'error'|'success'|''>('')
  const [busy, setBusy] = useState(false)

  // If already authenticated, do not show register
  useEffect(()=>{
    (async()=>{
      try{
        const me = await getMe()
        if((me as any)?.auth) {
          window.location.replace('/app/chat')
        }
      }catch{}
    })()
  },[])

  const u = useMemo(()=> (username || '').trim().toLowerCase(), [username])
  const e = useMemo(()=> (email || '').trim().toLowerCase(), [email])

  const usernameOk = useMemo(()=> /^[a-z0-9._-]{3,50}$/.test(u), [u])
  const emailOk = useMemo(()=> /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(e), [e])
  const pwOk = useMemo(()=> (password || '').length >= MIN_PW, [password, MIN_PW])
  const pwMatchOk = useMemo(()=> !!password2 && password2 === password, [password2, password])
  const formOk = usernameOk && emailOk && pwOk && pwMatchOk

  const pwStrength = useMemo(() => {
    const p = password || ''
    let score = 0
    if (p.length >= MIN_PW) score++
    if (/[a-zA-Z]/.test(p)) score++
    if (/[0-9]/.test(p)) score++
    if (/[^a-zA-Z0-9]/.test(p)) score++
    const label = score <= 1 ? 'sehr schwach' : score === 2 ? 'ok' : score === 3 ? 'gut' : 'stark'
    return { score, label }
  }, [password, MIN_PW])

  const fieldErrors = useMemo(()=>{
    const errs: string[] = []
    if(u && !usernameOk) errs.push('Username: min. 3 Zeichen, nur a-z, 0-9, Punkt, Unterstrich, Bindestrich.')
    if(e && !emailOk) errs.push('E-Mail: bitte eine gültige Adresse eingeben.')
    if(password && !pwOk) errs.push(`Passwort: mindestens ${MIN_PW} Zeichen.`)
    if(password2 && !pwMatchOk) errs.push('Passwort wiederholen: muss übereinstimmen.')
    return errs
  }, [u, usernameOk, e, emailOk, password, pwOk, password2, pwMatchOk, MIN_PW])

  async function parseApiError(res: Response): Promise<string> {
    try{
      const data = await res.json().catch(()=> null)
      const detail = (data as any)?.detail
      if(typeof detail === 'string') {
        if(detail === 'username_exists') return 'Dieser Username ist leider schon vergeben.'
        if(detail === 'email_exists') return 'Diese E‑Mail ist bereits registriert.'
        if(detail === 'invalid_username') return 'Username ist ungültig. Erlaubt: a-z, 0-9, . _ -'
        if(detail === 'missing_fields') return 'Bitte fülle alle Pflichtfelder aus.'
        if(detail.startsWith('password_too_short:')) {
          const n = Number(detail.split(':')[1] || MIN_PW)
          return `Passwort ist zu kurz (min. ${n} Zeichen).`
        }
        if(detail === 'rate_limited') return 'Zu viele Versuche – bitte kurz warten und erneut probieren.'
        return detail
      }
    }catch{}
    const txt = await res.text().catch(()=> '')
    return txt || 'Registrierung fehlgeschlagen'
  }

  async function onSubmit(e: React.FormEvent){
    e.preventDefault()
    setMsg(''); setMsgKind(''); setBusy(true)
    try{
      const res = await fetch('/api/register', {
        method: 'POST',
        credentials: 'include',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: name.trim() || undefined, username: u, email: e, password })
      })
      if(!res.ok){
        throw new Error(await parseApiError(res))
      }
      await res.json().catch(()=> ({} as any))

      // If backend set a session cookie (auto-login), go straight to /app/chat.
      try{
        const me = await getMe()
        if((me as any)?.auth){
          setMsg('Account erstellt ✅ Weiterleitung …')
          setMsgKind('success')
          setTimeout(()=>{ window.location.replace('/app/chat') }, 600)
          return
        }
      }catch{}

      setMsg('Account erstellt ✅ Du kannst dich jetzt einloggen.')
      setMsgKind('success')
    }catch(err:any){
      setMsg(err?.message || 'Registrierung fehlgeschlagen')
      setMsgKind('error')
    }
    finally{ setBusy(false) }
  }

  return (
    <div className="relative">
      <div
        className="pointer-events-none absolute inset-0 -z-10"
        style={{
          background:
            'radial-gradient(900px 420px at 20% 10%, rgba(37,99,235,0.14), transparent 60%), radial-gradient(900px 420px at 80% 0%, rgba(147,51,234,0.14), transparent 55%)',
        }}
      />

      <div className="max-w-md mx-auto grid gap-4">
        <KianaCard>
          <div className="text-lg font-semibold">Account erstellen</div>
          <div className="small mt-1">Ein paar Details – dann geht’s direkt in den Chat.</div>
        </KianaCard>

        <KianaCard>
          {fieldErrors.length > 0 && (
            <div className="kiana-alert kiana-alert-error mb-4">
              <div className="font-semibold">Bitte prüfen:</div>
              <ul className="mt-2 grid gap-1">
                {fieldErrors.map((t, i)=>(
                  <li key={i} className="small">• {t}</li>
                ))}
              </ul>
            </div>
          )}

          {msg && (
            <div className={`kiana-alert ${msgKind === 'success' ? 'kiana-alert-success' : msgKind === 'error' ? 'kiana-alert-error' : ''} mb-4`}>
              <div className="small">{msg}</div>
              {msgKind === 'success' && (
                <div className="mt-3 flex items-center gap-3 flex-wrap">
                  <a href="/login"><KianaButton>Weiter zum Login</KianaButton></a>
                  <a href="/app/chat"><KianaButton variant="primary">Zur App</KianaButton></a>
                </div>
              )}
            </div>
          )}

          <form className="form" onSubmit={onSubmit}>
            <label>
              <div className="small">Name (optional)</div>
              <input className="input" value={name} onChange={e=>setName(e.target.value)} placeholder="Gerald" />
            </label>
            <label>
              <div className="small">Username</div>
              <input
                className="input"
                value={username}
                onChange={e=>setUsername(e.target.value.toLowerCase())}
                placeholder="gerald"
                required
              />
            </label>
            <label>
              <div className="small">E-Mail</div>
              <input className="input" type="email" value={email} onChange={e=>setEmail(e.target.value)} required />
            </label>
            <label>
              <div className="small">Passwort</div>
              <input className="input" type="password" value={password} onChange={e=>setPassword(e.target.value)} required />
              <div className="small mt-2" style={{opacity:0.8}}>
                Mindestens {MIN_PW} Zeichen. Stärke: <span style={{ fontWeight: 700 }}>{pwStrength.label}</span>
              </div>
              <div className="mt-2" style={{ height: 10, borderRadius: 999, background: 'rgba(123,140,255,0.12)', border: '1px solid rgba(123,140,255,0.16)', overflow: 'hidden' }}>
                <div
                  style={{
                    height: '100%',
                    width: `${Math.min(100, Math.max(0, (pwStrength.score / 4) * 100))}%`,
                    background: 'var(--kiana-gradient-primary)',
                    transition: 'width 180ms ease',
                  }}
                />
              </div>
            </label>
            <label>
              <div className="small">Passwort wiederholen</div>
              <input className="input" type="password" value={password2} onChange={e=>setPassword2(e.target.value)} required />
            </label>
            <KianaButton variant="primary" disabled={busy || !formOk} type="submit">
              {busy ? 'Erstellen …' : 'Account erstellen'}
            </KianaButton>
          </form>

          <div className="small mt-4" style={{opacity:0.75}}>
            Schon ein Konto? <Link className="underline" href="/login">Login</Link>
          </div>
        </KianaCard>
      </div>
    </div>
  )
}
