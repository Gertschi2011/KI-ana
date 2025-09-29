'use client'
import { useState } from 'react'
import { API } from '../../lib/api'

export default function IngestPage(){
  const [url, setUrl] = useState('https://example.com')
  const [msg, setMsg] = useState('')

  async function submitCrawl(e: React.FormEvent){
    e.preventDefault()
    setMsg('')
    try{
      const r = await API.post<any>('/api/ingest/crawl', {url})
      setMsg('Crawl job: ' + r.job_id)
    }catch(err:any){ setMsg('Fehler: ' + String(err)) }
  }

  return (
    <div>
      <h1>Ingest</h1>
      <form onSubmit={submitCrawl} style={{display:'grid', gap:8, maxWidth:420}}>
        <input value={url} onChange={e=>setUrl(e.target.value)} placeholder='https://...'/>
        <button type='submit'>Crawl starten</button>
      </form>
      <div style={{marginTop:8}}>{msg}</div>
    </div>
  )
}
