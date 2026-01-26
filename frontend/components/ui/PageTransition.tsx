'use client'

import * as React from 'react'
import { AnimatePresence, motion, useReducedMotion } from 'framer-motion'
import { usePathname } from 'next/navigation'
import { KIANA_MOTION, kianaTransitionLong } from './motionTokens'

export default function PageTransition({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() || ''
  const reducedMotion = useReducedMotion()

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={pathname}
        initial={{ opacity: 0, y: reducedMotion ? 0 : KIANA_MOTION.y.medium }}
        animate={{ opacity: 1, y: 0 }}
        exit={{ opacity: 0, y: reducedMotion ? 0 : -KIANA_MOTION.y.medium }}
        transition={kianaTransitionLong()}
        style={{ willChange: 'transform, opacity' }}
      >
        {children}
      </motion.div>
    </AnimatePresence>
  )
}
