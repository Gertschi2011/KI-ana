'use client'

import * as React from 'react'
import { motion, type HTMLMotionProps, useReducedMotion } from 'framer-motion'
import { kianaCx } from './kianaCx'
import { KIANA_MOTION, kianaRevealFadeUp, kianaTransitionMicro } from './motionTokens'

export type KianaCardProps = HTMLMotionProps<'div'> & {
  hover?: boolean
  reveal?: boolean
}

export default function KianaCard({ hover = true, reveal = true, className, ...props }: KianaCardProps) {
  const reducedMotion = useReducedMotion()
  const motionProps = reveal
    ? kianaRevealFadeUp(!!reducedMotion)
    : {}

  return (
    <motion.div
      {...motionProps}
      whileHover={
        hover
          ? {
              scale: reducedMotion ? 1 : KIANA_MOTION.scale.hover,
              boxShadow: 'var(--kiana-card-shadow-hover)',
              transition: kianaTransitionMicro(),
            }
          : undefined
      }
      whileFocus={
        hover
          ? {
              scale: reducedMotion ? 1 : KIANA_MOTION.scale.hover,
              boxShadow: 'var(--kiana-card-shadow-hover)',
              transition: kianaTransitionMicro(),
            }
          : undefined
      }
      className={kianaCx('kiana-card', className)}
      {...props}
    />
  )
}
