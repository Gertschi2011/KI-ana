"use client"
import { useEffect, useState } from 'react'
import { API } from '../../lib/api'
import { ChainBlockCard } from '../../components/ChainBlockCard'

export default function MemoryPage(){
  const [items, setItems] = useState<any[]>([])
  const [valid, setValid] = useState<boolean | null>(null)
  const [msg, setMsg] = useState('')

  async function load(){
    try{
      const r = await API.get<any>('/api/memory/blocks')
      setItems(r.items||[])
      setValid(!!r.valid)
    }catch(e:any){ setMsg('Fehler: '+String(e)) }
  }
  useEffect(()=>{ load() }, [])

  async function verify(){
    try{
      const r = await API.post<any>('/api/memory/verify', {})
      setValid(!!r.valid)
    }catch(e:any){ setMsg('Fehler: '+String(e)) }
  }

  return (
    <div>
      <h1>Memory Chain</h1>
      <div style={{marginBottom:8}}>
        <button onClick={load}>Neu laden</button>{' '}
        <button onClick={verify}>Verify</button>{' '}
        <span>Status: {valid===null? '—' : valid? 'OK' : 'BROKEN'}</span>
      </div>
      <div>{msg}</div>
      <div>{items.map((b,i)=>(<ChainBlockCard key={i} block={b}/>))}</div>
    </div>
  )
}
