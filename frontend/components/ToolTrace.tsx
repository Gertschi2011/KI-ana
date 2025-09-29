type Trace = { tool: string; args: any; output: any; duration_ms: number; status: string }
export function ToolTrace({ trace }: { trace: Trace }){
  return (
    <div style={{border:'1px solid #eee', borderRadius:8, padding:12, margin:'8px 0'}}>
      <div style={{display:'flex', justifyContent:'space-between'}}>
        <strong>Tool: {trace.tool}</strong>
        <span>{trace.duration_ms} ms · {trace.status}</span>
      </div>
      <pre style={{background:'#fafafa', padding:8, borderRadius:6, overflow:'auto'}}>{JSON.stringify(trace.args, null, 2)}</pre>
      <pre style={{background:'#f7fbff', padding:8, borderRadius:6, overflow:'auto'}}>{JSON.stringify(trace.output, null, 2)}</pre>
    </div>
  )
}
