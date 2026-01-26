export const KIANA_MOTION = {
  duration: {
    micro: 0.12,
    medium: 0.22,
    long: 0.38,
  },
  ease: {
    out: [0.16, 1, 0.3, 1] as const,
    in: [0.7, 0, 0.84, 0] as const,
    inOut: [0.65, 0, 0.35, 1] as const,
  },
  y: {
    micro: 6,
    medium: 12,
  },
  scale: {
    hover: 1.01,
    tap: 0.99,
  },
  opacity: {
    pulseMin: 0.92,
  },
} as const

export function kianaTransitionMicro() {
  return {
    type: 'tween' as const,
    duration: KIANA_MOTION.duration.micro,
    ease: KIANA_MOTION.ease.out,
  }
}

export function kianaTransitionMedium(delay: number = 0) {
  return {
    type: 'tween' as const,
    duration: KIANA_MOTION.duration.medium,
    ease: KIANA_MOTION.ease.out,
    delay,
  }
}

export function kianaTransitionLong() {
  return {
    type: 'tween' as const,
    duration: KIANA_MOTION.duration.long,
    ease: KIANA_MOTION.ease.out,
  }
}

export function kianaRevealFadeUp(reducedMotion: boolean, delay: number = 0) {
  return {
    initial: { opacity: 0, y: reducedMotion ? 0 : KIANA_MOTION.y.medium },
    animate: { opacity: 1, y: 0 },
    transition: kianaTransitionMedium(delay),
  }
}
