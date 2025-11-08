'use client'
import NavbarApp from '../../components/NavbarApp'
import '../globals.css'
import { useEffect } from 'react'
import { getMe } from '../../lib/api'

export default function AppLayout({ children }: { children: React.ReactNode }) {
  useEffect(()=>{
    // Enforce dark theme on app pages
    try{ document.documentElement.classList.add('dark') }catch{}
    ;(async()=>{
      try{
        const me = await getMe()
        if(!me?.auth){ window.location.replace('/login') }
      }catch{ window.location.replace('/login') }
    })()
  },[])

  return (
    <html lang="de">
      <body className="bg-gray-900 text-gray-100">
        <NavbarApp />
        <main className="p-8">{children}</main>
      </body>
    </html>
  )
}
