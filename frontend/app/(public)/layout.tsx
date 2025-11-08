"use client"
import '../globals.css'
import NavbarPublic from '../../components/NavbarPublic'
import { useEffect } from 'react'

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  useEffect(()=>{
    // Ensure public pages are always light themed
    try{ document.documentElement.classList.remove('dark') }catch{}
  },[])
  return (
    <html lang="de">
      <body className="bg-white text-gray-900">
        <script
          dangerouslySetInnerHTML={{ __html: "try{document.documentElement.classList.remove('dark')}catch(e){}" }}
        />
        <NavbarPublic />
        <main className="p-6">{children}</main>
      </body>
    </html>
  )
}
