'use client'
import { useEffect } from 'react'

export default function ToolsRemovedPage(){
  useEffect(()=>{
    // Redirect legacy route to app home
    if (typeof window !== 'undefined') {
      window.location.replace('/app')
    }
  },[])
  return (
    <div style={{padding:24}}>
      <h1>KI_ana</h1>
      <p>Diese Seite wurde entfernt. Weiterleitung zur App…</p>
      <a href="/app">Zur App</a>
    </div>
  )
}
