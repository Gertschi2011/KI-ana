'use client'
import { useEffect } from 'react'

export default function PricingPage(){
  useEffect(()=>{ window.location.replace('/static/pricing.html') }, [])
  return (
    <div className="max-w-3xl mx-auto p-6">
      <h1 className="text-2xl font-bold mb-2">Preise</h1>
      <p className="small">Weiterleitung… Falls nichts passiert, <a className="underline" href="/static/pricing.html">hier klicken</a>.</p>
    </div>
  )
}
