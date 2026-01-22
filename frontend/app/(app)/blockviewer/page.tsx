export default function BlockViewerPage(){
  return (
    <div className="max-w-6xl mx-auto grid gap-4">
      <div className="card">
        <div className="text-lg font-semibold">🧱 Block Viewer</div>
        <div className="small mt-1">Viewer wird unten eingebettet.</div>
      </div>

      <div className="card" style={{ padding: 0, overflow: 'hidden' }}>
        <iframe
          title="Block Viewer"
          src="/static/block_viewer.html"
          style={{ width: '100%', height: '75vh', border: 0, background: 'white' }}
        />
      </div>
    </div>
  )
}
