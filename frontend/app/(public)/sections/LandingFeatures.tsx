'use client'

import { motion } from 'framer-motion'
import KianaCard from '../../../components/ui/KianaCard'

const FEATURES = [
  {
    t: '🧠 Sie erinnert sich – wirklich.',
    d: 'Nicht nur „dieses Gespräch“. Sondern dich. Stück für Stück.',
  },
  {
    t: '🤝 Sie fragt nach, statt zu raten.',
    d: 'Wenn etwas wichtig klingt, fragt KI_ana kurz nach – damit sie richtig lernt.',
  },
  {
    t: '🌱 Sie wächst mit dir.',
    d: 'Mit jedem Chat entsteht mehr Vertrauen, mehr Kontext, mehr Gefühl.',
  },
] as const

export default function LandingFeatures() {
  return (
    <motion.div
      initial="hidden"
      whileInView="show"
      viewport={{ once: true, margin: '-80px' }}
      variants={{ hidden: { opacity: 0 }, show: { opacity: 1, transition: { staggerChildren: 0.08 } } }}
      className="grid gap-4 md:grid-cols-3"
    >
      {FEATURES.map((x) => (
        <motion.div key={x.t} variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }}>
          <KianaCard>
            <div className="text-base font-semibold">{x.t}</div>
            <div className="small mt-2">{x.d}</div>
          </KianaCard>
        </motion.div>
      ))}
    </motion.div>
  )
}
