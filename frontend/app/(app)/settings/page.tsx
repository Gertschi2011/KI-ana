'use client'
import { useEffect, useState } from 'react'
import KianaCard from '../../../components/ui/KianaCard'
import KianaButton from '../../../components/ui/KianaButton'

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
    <div className="max-w-3xl mx-auto grid gap-4">
      <KianaCard>
        <div>
          <div className="text-lg font-semibold">Einstellungen</div>
          <div className="small mt-1">Mach KI_ana so, wie es sich für dich gut anfühlt.</div>
          <div className="small mt-2" style={{ opacity: 0.85 }}>
            Diese Einstellungen bleiben auf diesem Gerät.
          </div>
        </div>
        <label className="block">
          <div className="mb-1">Stimme</div>
          <select className="input" value={voice} onChange={e=>setVoice(e.target.value)}>
            <option value="neutral">Neutral</option>
            <option value="freundlich">Freundlich</option>
            <option value="formal">Formal</option>
          </select>
          <div className="small mt-1" style={{ opacity: 0.75 }}>
            Wie KI_ana klingt – ruhig, warm, klar.
          </div>
        </label>
        <label className="block">
          <div className="mb-1">Antwortstil</div>
          <select className="input" value={style} onChange={e=>setStyle(e.target.value)}>
            <option value="balanced">Ausgewogen</option>
            <option value="concise">Kurz</option>
            <option value="detailed">Ausführlich</option>
          </select>
          <div className="small mt-1" style={{ opacity: 0.75 }}>
            Kurz zum Atmen – oder lieber mit mehr Tiefe.
          </div>
        </label>
        <label className="flex items-center gap-3">
          <input type="checkbox" checked={webOk} onChange={(e)=>setWebOk(e.target.checked)} />
          <div>
            <div className="font-medium">Aktuelles Wissen aus dem Web</div>
            <div className="small">
              Wenn du willst, schaut KI_ana bei Fragen zu „aktuell / News / prüfen“ kurz nach. Sonst bleibt sie bei dem, was sie schon weiß.
            </div>
          </div>
        </label>
        <div className="kiana-inset mt-3">
          <div className="font-semibold">Gedächtnis & Datenschutz</div>
          <div className="small mt-1" style={{ opacity: 0.9 }}>
            KI_ana versucht dich zu verstehen – aber sie merkt sich Dinge nur, wenn du das möchtest.
          </div>
          <div className="small mt-2" style={{ opacity: 0.85 }}>
            Wenn etwas „bleiben“ soll, fragt KI_ana sanft nach. Und wenn etwas nur ein Moment war, darf es auch wieder gehen.
          </div>
        </div>
        <div className="mt-2">
          <KianaButton variant="primary" onClick={save}>Speichern</KianaButton>
        </div>
        {msg ? (
          <div className="kiana-inset mt-3" role="status">
            <div className="small">{msg}</div>
          </div>
        ) : null}
      </KianaCard>
    </div>
  )
}
