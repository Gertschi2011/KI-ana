import KianaCard from '../../../components/ui/KianaCard'

export default function BlockViewerPage(){
  return (
    <div className="max-w-6xl mx-auto grid gap-4">
      <KianaCard>
        <div className="text-lg font-semibold">Block Viewer</div>
        <div className="small mt-1">Der Viewer läuft eingebettet (ohne Legacy‑Navbar).</div>
      </KianaCard>

      <KianaCard hover={false} reveal={false} className="p-0 overflow-hidden">
        <iframe
          title="Block Viewer"
          src="/static/block_viewer.html?embed=1"
          style={{ width: '100%', height: '75vh', border: 0, background: 'white' }}
        />
      </KianaCard>
    </div>
  )
}
