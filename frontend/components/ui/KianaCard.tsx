'use client'

import * as React from 'react'
import { motion, type HTMLMotionProps } from 'framer-motion'
import { kianaCx } from './kianaCx'

export type KianaCardProps = HTMLMotionProps<'div'> & {
  hover?: boolean
  reveal?: boolean
}

export default function KianaCard({ hover = true, reveal = true, className, ...props }: KianaCardProps) {
  const motionProps = reveal
    ? {
        initial: { opacity: 0, y: 12 },
        animate: { opacity: 1, y: 0 },
        transition: { duration: 0.35, ease: 'easeOut' },
      }
    : {}

  return (
    <motion.div
      {...motionProps}
      whileHover={
        hover
          ? {
              y: -2,
              scale: 1.01,
              boxShadow: 'var(--kiana-card-shadow-hover)',
            }
          : undefined
      }
      className={kianaCx('kiana-card', className)}
      {...props}
    />
  )
}
