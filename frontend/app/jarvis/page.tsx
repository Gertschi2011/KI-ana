'use client'
import { useState } from 'react'
import { API } from '../../lib/api'
import { ToolTrace } from '../../components/ToolTrace'

export default function JarvisPage(){
  const [tool, setTool] = useState('echo')
  const [args, setArgs] = useState('{"text":"Hallo KI_ana"}')
  const [trace, setTrace] = useState<any>(null)
  const [msg, setMsg] = useState('')

  async function run(e: React.FormEvent){
    e.preventDefault()
    setMsg(''); setTrace(null)
    try{
      const body = { tool, args: JSON.parse(args) }
      const r = await API.post<any>('/api/jarvis/invoke', body)
      if(!r.ok){ setMsg('Fehler: ' + (r.error||'unknown')); return }
      setTrace(r.trace)
    }catch(err:any){ setMsg('Fehler: ' + String(err)) }
  }

  return (
    <div>
      <h1>Jarvis</h1>
      <form onSubmit={run} style={{display:'grid', gap:8, maxWidth:560}}>
        <label>Tool
          <select value={tool} onChange={e=>setTool(e.target.value)}>
            <option value='echo'>echo</option>
            <option value='sleep'>sleep</option>
          </select>
        </label>
        <label>Args (JSON)
          <textarea value={args} onChange={e=>setArgs(e.target.value)} rows={6} style={{width:'100%'}} />
        </label>
        <button type='submit'>Ausführen</button>
      </form>
      <div style={{marginTop:8}}>{msg}</div>
      {trace && (<ToolTrace trace={trace} />)}
    </div>
  )
}
