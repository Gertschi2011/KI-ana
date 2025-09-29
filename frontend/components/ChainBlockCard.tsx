export function ChainBlockCard({ block }: { block: any }){
  const h = String(block?.hash || '').slice(0, 12)
  const ts = block?.ts ? new Date(block.ts*1000).toLocaleString() : '—'
  return (
    <div style={{border:'1px solid #eee', borderRadius:8, padding:12, margin:'8px 0'}}>
      <div style={{display:'flex', gap:12, alignItems:'baseline'}}>
        <strong>{block?.type || 'UNKNOWN'}</strong>
        <span style={{opacity:.7}}>hash: {h}…</span>
        <span style={{opacity:.7}}>ts: {ts}</span>
        <span style={{opacity:.7}}>source: {block?.source || 'n/a'}</span>
      </div>
      <pre style={{background:'#fafafa', padding:8, borderRadius:6, overflow:'auto'}}>{JSON.stringify(block?.content||{}, null, 2)}</pre>
      {Array.isArray(block?.tags) && block.tags.length>0 && (
        <div style={{display:'flex', gap:6, flexWrap:'wrap'}}>{block.tags.map((t:string,i:number)=>(
          <span key={i} style={{background:'#f3f3f3', padding:'2px 6px', borderRadius:12, fontSize:12}}>{t}</span>
        ))}</div>
      )}
    </div>
  )
}
