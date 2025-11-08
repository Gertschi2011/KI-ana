'use client'
import { useEffect, useState } from 'react'

export default function SettingsPage(){
  const [voice, setVoice] = useState('neutral')
  const [style, setStyle] = useState('balanced')
  const [msg, setMsg] = useState('')

  useEffect(()=>{ // load user prefs (placeholder)
    try{
      const v = localStorage.getItem('kiana_voice') || 'neutral'
      const s = localStorage.getItem('kiana_style') || 'balanced'
      setVoice(v); setStyle(s)
    }catch{}
  },[])

  function save(){
    try{
      localStorage.setItem('kiana_voice', voice)
      localStorage.setItem('kiana_style', style)
      setMsg('Gespeichert')
      setTimeout(()=>setMsg(''), 800)
    }catch{ setMsg('Konnte nicht speichern') }
  }

  return (
    <div className="max-w-xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-4">Einstellungen</h1>
      <div className="card grid gap-4">
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
        <div>
          <button className="btn-dark" onClick={save}>Speichern</button>
        </div>
        {msg && <div className="small">{msg}</div>}
      </div>
    </div>
  )
}
