'use client'
import { useEffect, useState } from 'react'

export default function PapaPage(){
  const [msg, setMsg] = useState('')

  useEffect(()=>{
    setMsg('Willkommen bei Papa 👨‍🍼 – nur für eingeloggte Nutzer sichtbar.')
  },[])

  return (
    <div className="max-w-3xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-2">Papa</h1>
      <div className="card">
        <p className="mb-2">{msg}</p>
        <p className="small">Hier kannst du bald personalisierte Inhalte sehen.</p>
      </div>
    </div>
  )
}
