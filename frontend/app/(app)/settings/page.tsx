'use client'
import { useEffect, useState } from 'react'

export default function SettingsPage(){
  const [voice, setVoice] = useState('neutral')
  const [style, setStyle] = useState('balanced')
  const [webOk, setWebOk] = useState(false)
  const [msg, setMsg] = useState('')

  useEffect(()=>{ // load user prefs (placeholder)
    try{
      const v = localStorage.getItem('kiana_voice') || 'neutral'
      const s = localStorage.getItem('kiana_style') || 'balanced'
      const w = localStorage.getItem('kiana_web_ok') || '0'
      setVoice(v); setStyle(s)
      setWebOk(w === '1')
    }catch{}
  },[])

  function save(){
    try{
      localStorage.setItem('kiana_voice', voice)
      localStorage.setItem('kiana_style', style)
      localStorage.setItem('kiana_web_ok', webOk ? '1' : '0')
      setMsg('Gespeichert')
      setTimeout(()=>setMsg(''), 800)
    }catch{ setMsg('Konnte nicht speichern') }
  }

  return (
    <div className="max-w-3xl mx-auto">
      <div className="card grid gap-4">
        <div>
          <div className="text-lg font-semibold">Einstellungen</div>
          <div className="small mt-1">Passe Stil, Stimme und Web-Recherche an. Diese Einstellungen werden lokal gespeichert.</div>
        </div>
        <label className="block">
          <div className="mb-1">TTS Stimme</div>
          <select className="input" value={voice} onChange={e=>setVoice(e.target.value)}>
            <option value="neutral">Neutral</option>
            <option value="freundlich">Freundlich</option>
            <option value="formal">Formal</option>
          </select>
        </label>
        <label className="block">
          <div className="mb-1">Antwortstil</div>
          <select className="input" value={style} onChange={e=>setStyle(e.target.value)}>
            <option value="balanced">Ausgewogen</option>
            <option value="concise">Kurz</option>
            <option value="detailed">Ausführlich</option>
          </select>
        </label>
        <label className="flex items-center gap-3">
          <input type="checkbox" checked={webOk} onChange={(e)=>setWebOk(e.target.checked)} />
          <div>
            <div className="font-medium">Web-Recherche erlauben (für mich)</div>
            <div className="small">Nur für „aktuell/news/verifizieren“-Fragen wird Web genutzt.</div>
          </div>
        </label>
        <div>
          <button className="kiana-btn kiana-btn-primary" onClick={save}>Speichern</button>
        </div>
        {msg && <div className="small">{msg}</div>}
      </div>
    </div>
  )
}
