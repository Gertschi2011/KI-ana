import { headers } from 'next/headers'
import { notFound } from 'next/navigation'

function originFromRequest(): string {
  const h = headers()
  const host = h.get('host') || ''
  const proto = (h.get('x-forwarded-proto') || 'https').split(',')[0].trim() || 'https'
  if (!host) return 'https://ki-ana.at'
  return `${proto}://${host}`
}

export const dynamic = 'force-dynamic'

export default async function BuildProofPage() {
  const origin = originFromRequest()
  const cookie = headers().get('cookie') || ''
  const meRes = await fetch(`${origin}/api/me`, {
    method: 'GET',
    headers: {
      cookie,
      accept: 'application/json',
    },
    cache: 'no-store',
  }).catch(() => null)

  const meJson: any = meRes ? await meRes.json().catch(() => null) : null
  const authed = !!meJson?.auth
  const user = authed ? (meJson?.user || null) : null

  const role = String(user?.role || '').toLowerCase()
  const roles = Array.isArray(user?.roles) ? user.roles.map((r: any) => String(r).toLowerCase()) : []
  const isAdmin = !!user?.is_admin || roles.includes('admin') || role === 'admin'
  const isCreator = !!user?.is_creator || roles.includes('creator') || role === 'creator'

  if (!authed || !(isAdmin || isCreator)) {
    notFound()
  }

  const sha = (process.env.NEXT_PUBLIC_BUILD_SHA || 'unknown').slice(0, 12)

  return (
    <main style={{ padding: 24, fontFamily: 'ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace' }}>
      Build {sha}
    </main>
  )
}
