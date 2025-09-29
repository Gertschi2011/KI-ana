"use client"
import { useEffect, useState } from 'react'

export function VoiceToggle(){
  const [on, setOn] = useState(false)
  const [utt, setUtt] = useState<SpeechSynthesisUtterance | null>(null)

  useEffect(()=>{
    if(!on){ if(utt){ window.speechSynthesis.cancel(); setUtt(null) } return }
    const u = new SpeechSynthesisUtterance('Sprachmodus aktiv.')
    window.speechSynthesis.speak(u)
    setUtt(u)
  }, [on])

  return (
    <button onClick={()=>setOn(v=>!v)}>
      {on ? '🔊 Voice ON' : '🔇 Voice OFF'}
    </button>
  )
}
