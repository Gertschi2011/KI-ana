'use client'
import Navbar from '../../components/Navbar'
import '../globals.css'
import { useEffect } from 'react'
import { getMe } from '../../lib/api'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  useEffect(()=>{
    // Enforce light theme on app pages
    try{ document.documentElement.classList.remove('dark') }catch{}
    ;(async()=>{
      try{
        const me = await getMe()
        if(!me?.auth){ window.location.replace('/login') }
      }catch{ window.location.replace('/login') }
    })()
  },[])

  return (
    <html lang="de">
      <body style={{ background: 'var(--k-bg)', color: 'var(--k-text)' }}>
        <script
          dangerouslySetInnerHTML={{ __html: "try{document.documentElement.classList.remove('dark')}catch(e){}" }}
        />
        <Navbar />
        <main className="max-w-6xl mx-auto px-4 py-8">{children}</main>
      </body>
    </html>
  )
}
