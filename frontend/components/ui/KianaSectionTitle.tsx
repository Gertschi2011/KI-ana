'use client'

import * as React from 'react'
import { motion, useReducedMotion } from 'framer-motion'
import { kianaCx } from './kianaCx'
import { KIANA_MOTION, kianaTransitionMedium } from './motionTokens'

export type KianaSectionTitleProps = {
  title: React.ReactNode
  subtitle?: React.ReactNode
  className?: string
  align?: 'left' | 'center'
}

export default function KianaSectionTitle({ title, subtitle, className, align = 'center' }: KianaSectionTitleProps) {
  const isCenter = align === 'center'
  const reducedMotion = useReducedMotion()
  return (
    <motion.div
      initial={{ opacity: 0, y: reducedMotion ? 0 : KIANA_MOTION.y.micro }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={kianaTransitionMedium()}
      className={kianaCx(isCenter ? 'text-center' : 'text-left', className)}
    >
      <div className="kiana-section-title">{title}</div>
      {subtitle ? <div className="kiana-section-subtitle">{subtitle}</div> : null}
    </motion.div>
  )
}
