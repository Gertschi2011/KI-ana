"use client"
import '../globals.css'
import Navbar from '../../components/Navbar'
import { useEffect } from 'react'

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  useEffect(()=>{
    // Ensure public pages are always light themed
    try{ document.documentElement.classList.remove('dark') }catch{}
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
