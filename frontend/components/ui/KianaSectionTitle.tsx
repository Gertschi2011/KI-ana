'use client'

import * as React from 'react'
import { motion } from 'framer-motion'
import { kianaCx } from './kianaCx'

export type KianaSectionTitleProps = {
  title: React.ReactNode
  subtitle?: React.ReactNode
  className?: string
  align?: 'left' | 'center'
}

export default function KianaSectionTitle({ title, subtitle, className, align = 'center' }: KianaSectionTitleProps) {
  const isCenter = align === 'center'
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: '-80px' }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
      className={kianaCx(isCenter ? 'text-center' : 'text-left', className)}
    >
      <div className="kiana-section-title">{title}</div>
      {subtitle ? <div className="kiana-section-subtitle">{subtitle}</div> : null}
    </motion.div>
  )
}
