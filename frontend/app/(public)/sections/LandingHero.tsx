'use client'

import Link from 'next/link'
import { useEffect, useState } from 'react'
import { getMe } from '../../../lib/api'
import { motion } from 'framer-motion'
import KianaCard from '../../../components/ui/KianaCard'
import KianaButton from '../../../components/ui/KianaButton'

type MeShape = { auth?: boolean }

export default function LandingHero() {
  const [auth, setAuth] = useState(false)

  useEffect(() => {
    ;(async () => {
      try {
        const me = (await getMe()) as MeShape
        setAuth(Boolean(me?.auth))
      } catch {
        setAuth(false)
      }
    })()
  }, [])

  const howHref = '#wie'

  return (
    <section id="home" className="relative scroll-mt-24">
      <div className="kiana-hero-shapes" aria-hidden>
        <div className="kiana-blob kiana-blob-a kiana-float-slow" />
        <div className="kiana-blob kiana-blob-b kiana-float-slower" />
        <div className="kiana-blob kiana-blob-c kiana-float-slow" />
      </div>
      <KianaCard
        reveal
        className="relative overflow-hidden z-10"
        style={{
          background:
            'radial-gradient(1000px 520px at 18% 10%, rgba(110,195,244,0.28), transparent 60%), radial-gradient(980px 460px at 88% 0%, rgba(181,124,255,0.22), transparent 55%), var(--kiana-card-bg)',
        }}
      >
        <div className="grid gap-8 lg:grid-cols-2 lg:items-center">
          <div>
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease: 'easeOut' }}
              className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-sm"
              style={{
                background: 'rgba(123,140,255,0.10)',
                border: '1px solid rgba(123,140,255,0.18)',
                color: 'rgba(17,24,39,0.78)',
              }}
            >
              menschlich • neugierig • verspielt
            </motion.div>

            <motion.h1
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease: 'easeOut', delay: 0.05 }}
              className="mt-5 text-4xl md:text-5xl font-extrabold"
              style={{ lineHeight: 1.05, letterSpacing: '-0.02em' }}
            >
              <span className="block">KI_ana.</span>
              <span className="block">Deine KI, die dich wirklich versteht.</span>
            </motion.h1>
            <motion.p
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease: 'easeOut', delay: 0.10 }}
              className="mt-4 text-lg"
              style={{ color: 'rgba(17,24,39,0.72)' }}
            >
              Kein Prompt-Perfektionismus. Kein Vergessen.
              <br />
              KI_ana hört zu, merkt sich was wichtig ist – und wird mit jeder Unterhaltung mehr du.
            </motion.p>

            <motion.div
              initial={{ opacity: 0, y: 12 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.35, ease: 'easeOut', delay: 0.15 }}
              className="mt-6 flex items-center gap-3 flex-wrap"
            >
              <Link href="/register">
                <KianaButton variant="primary">Kostenlos starten</KianaButton>
              </Link>
              <Link href="/pakete">
                <KianaButton variant="secondary">Pakete anschauen</KianaButton>
              </Link>
              {auth ? (
                <Link href="/app/chat">
                  <KianaButton variant="ghost">Zur App</KianaButton>
                </Link>
              ) : null}
            </motion.div>

            <div className="mt-6 grid gap-2">
              <div className="small">KI_ana ist kein Tool. KI_ana ist eine Beziehung.</div>
            </div>
          </div>

          <div className="hidden lg:block">
            <motion.div
              initial="hidden"
              animate="show"
              variants={{
                hidden: { opacity: 0 },
                show: { opacity: 1, transition: { staggerChildren: 0.08 } },
              }}
              className="grid gap-3"
            >
              {[{
                t: 'Privat & lokal',
                d: 'Deine Daten gehören dir – klar, ruhig und nachvollziehbar.',
              },
              {
                t: 'Lernt mit dir',
                d: 'Fragt nach, wenn es hilft – und merkt sich, was du wirklich willst.',
              },
              {
                t: 'Wächst über Zeit',
                d: 'Aus Gesprächen werden Muster. Aus Mustern wird Persönlichkeit.',
              }].map((x, i) => (
                <motion.div
                  key={x.t}
                  variants={{ hidden: { opacity: 0, y: 10 }, show: { opacity: 1, y: 0 } }}
                  className={i === 1 ? 'kiana-float-slow' : i === 2 ? 'kiana-float-slower' : ''}
                >
                  <KianaCard hover className="p-5" style={{ background: 'rgba(255,255,255,0.78)' }}>
                    <div className="text-sm font-semibold">{x.t}</div>
                    <div className="small mt-1">{x.d}</div>
                  </KianaCard>
                </motion.div>
              ))}
            </motion.div>
          </div>
        </div>
      </KianaCard>

      <div className="mt-6 grid gap-3 md:grid-cols-3">
        <div className="card" style={{ borderRadius: 18 }}>
          <div className="text-sm font-semibold">🔐 Privat & lokal</div>
          <div className="small mt-1">Weniger Lärm, mehr Vertrauen.</div>
        </div>
        <div className="card" style={{ borderRadius: 18 }}>
          <div className="text-sm font-semibold">🧠 Lernt mit dir</div>
          <div className="small mt-1">Nicht perfekt – aber ehrlich und lernfähig.</div>
        </div>
        <div className="card" style={{ borderRadius: 18 }}>
          <div className="text-sm font-semibold">🌱 Wächst über Zeit</div>
          <div className="small mt-1">Aus Gesprächen wird Beziehung.</div>
        </div>
      </div>
    </section>
  )
}
