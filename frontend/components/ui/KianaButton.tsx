'use client'

import * as React from "react";
import { motion, type HTMLMotionProps } from "framer-motion";

import { kianaCx } from './kianaCx'

export type KianaButtonVariant = 'primary' | 'secondary' | 'ghost'

export type KianaButtonProps = HTMLMotionProps<"button"> & {
  variant?: KianaButtonVariant
  size?: 'sm' | 'md' | 'lg'
}

export function KianaButton({ variant = 'primary', size = 'md', className = '', ...props }: KianaButtonProps) {
  const base = 'kiana-btn2'
  const v =
    variant === 'primary'
      ? 'kiana-btn2-primary'
      : variant === 'ghost'
        ? 'kiana-btn2-ghost'
        : 'kiana-btn2-secondary'
  const s = size === 'sm' ? 'px-3 py-2 text-sm' : size === 'lg' ? 'px-5 py-3 text-base' : ''

  return (
    <motion.button
      whileTap={{ scale: 0.96 }}
      whileHover={{ filter: 'brightness(1.03)' }}
      transition={{ duration: 0.12, ease: 'easeOut' }}
      className={kianaCx(base, v, s, className)}
      {...props}
    />
  )
}

export default KianaButton
