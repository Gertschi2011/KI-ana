'use client'
import Navbar from '../../components/Navbar'
import { useEffect } from 'react'
import { getMe } from '../../lib/api'
import PageTransition from '../../components/ui/PageTransition'

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
    <>
      <script
        dangerouslySetInnerHTML={{ __html: "try{document.documentElement.classList.remove('dark')}catch(e){}" }}
      />
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-8">
        <PageTransition>{children}</PageTransition>
      </main>
    </>
  )
}
