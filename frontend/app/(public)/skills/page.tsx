'use client'
import { useEffect } from 'react'

export default function SkillsPage(){
  useEffect(()=>{ window.location.replace('/static/skills.html') }, [])
  return (
    <div className="max-w-3xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-2">Fähigkeiten</h1>
      <p className="small">Weiterleitung… Falls nichts passiert, <a className="underline" href="/static/skills.html">hier klicken</a>.</p>
    </div>
  )
}
