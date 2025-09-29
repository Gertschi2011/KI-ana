'use client'
import { useState } from 'react'
import { API } from '../../lib/api'

export default function SearchPage(){
  const [q, setQ] = useState('hello world')
  const [items, setItems] = useState<any[]>([])
  const [msg, setMsg] = useState('')

  async function run(e: React.FormEvent){
    e.preventDefault()
    setMsg(''); setItems([])
    try{
      const r = await API.get<any>(`/api/search/?q=${encodeURIComponent(q)}`)
      setItems(r.items||[])
    }catch(err:any){ setMsg('Fehler: ' + String(err)) }
  }

  return (
    <div>
      <h1>Search</h1>
      <form onSubmit={run} style={{display:'flex', gap:8, margin:'8px 0'}}>
        <input value={q} onChange={e=>setQ(e.target.value)} placeholder='Query' style={{flex:1}}/>
        <button type='submit'>Suchen</button>
      </form>
      <div>{msg}</div>
      <ul>
        {items.map((it,i)=>(<li key={i}><code>{it.id}</code> — {it.text} ({it.score})</li>))}
      </ul>
    </div>
  )
}
