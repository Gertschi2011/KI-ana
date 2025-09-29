type Job = { id: string; status: string; progress?: number; message?: string }
export function JobStatus({ job }: { job: Job }){
  return (
    <div style={{border:'1px solid #eee', borderRadius:8, padding:10}}>
      <div><strong>Job:</strong> {job.id}</div>
      <div><strong>Status:</strong> {job.status}</div>
      {typeof job.progress === 'number' && (<div><strong>Progress:</strong> {job.progress}%</div>)}
      {job.message && (<div style={{opacity:.8}}>{job.message}</div>)}
    </div>
  )
}
