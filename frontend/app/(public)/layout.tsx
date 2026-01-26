"use client"

import { useEffect } from 'react'
import Navbar from '../../components/Navbar'
import PageTransition from '../../components/ui/PageTransition'
import { MotionConfig } from 'framer-motion'

export default function PublicLayout({ children }: { children: React.ReactNode }) {
  useEffect(() => {
    try {
      document.documentElement.classList.remove('dark')
    } catch {}
  }, [])

  return (
    <>
      <script
        dangerouslySetInnerHTML={{ __html: "try{document.documentElement.classList.remove('dark')}catch(e){}" }}
      />
      <Navbar />
      <main className="max-w-6xl mx-auto px-4 py-10">
        <MotionConfig reducedMotion="user">
          <PageTransition>{children}</PageTransition>
        </MotionConfig>
      </main>
    </>
  )
}
