'use client'

import * as React from "react";
import { motion, type HTMLMotionProps, useReducedMotion } from "framer-motion";

import { kianaCx } from './kianaCx'
import { KIANA_MOTION, kianaTransitionMicro } from './motionTokens'

export type KianaButtonVariant = 'primary' | 'secondary' | 'ghost'

export type KianaButtonProps = HTMLMotionProps<"button"> & {
  variant?: KianaButtonVariant
  size?: 'sm' | 'md' | 'lg'
}

export function KianaButton({ variant = 'primary', size = 'md', className = '', ...props }: KianaButtonProps) {
  const reducedMotion = useReducedMotion()
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
      whileHover={reducedMotion ? undefined : { scale: KIANA_MOTION.scale.hover }}
      whileFocus={reducedMotion ? undefined : { scale: KIANA_MOTION.scale.hover }}
      whileTap={reducedMotion ? undefined : { scale: KIANA_MOTION.scale.tap }}
      transition={kianaTransitionMicro()}
      className={kianaCx(base, v, s, className)}
      {...props}
    />
  )
}

export default KianaButton
