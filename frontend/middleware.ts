import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export const config = {
  matcher: [
    // Production nginx strips /app/* -> /* before Next.js.
    // So we must protect BOTH:
    // - the external /app/* prefix (direct-to-frontend)
    // - the internal "stripped" routes like /chat, /dashboard, ...
    '/app/:path*',
    '/chat',
    '/chat/:path*',
    '/dashboard',
    '/dashboard/:path*',
    '/settings',
    '/settings/:path*',
    '/papa',
    '/papa/:path*',
    '/tools',
    '/tools/:path*',
    '/monitoring',
    '/monitoring/:path*',
    '/blockviewer',
    '/blockviewer/:path*',
    '/admin',
    '/admin/:path*',
    '/buildproof',
    '/buildproof/:path*',
    // Auth routes remain public, but we redirect authed users away.
    '/login',
    '/register',
  ],
}

export async function middleware(req: NextRequest) {
  const url = req.nextUrl.clone()
  const pathname = url.pathname || '/'
  const isAppPrefixed = pathname === '/app' || pathname.startsWith('/app/')

  const forwardedProto = req.headers.get('x-forwarded-proto')
  const forwardedHost = req.headers.get('x-forwarded-host')
  const requestHost = forwardedHost || req.headers.get('host') || url.host
  const requestProto = forwardedProto || url.protocol.replace(':', '') || 'https'
  const requestOrigin = `${requestProto}://${requestHost}`

  const normalizedPathname = pathname.startsWith('/app/')
    ? pathname.slice('/app'.length)
    : pathname

  const isAuthPage =
    normalizedPathname === '/login' || normalizedPathname === '/register'

  const protectedPrefixes = [
    '/app',
    '/chat',
    '/dashboard',
    '/settings',
    '/papa',
    '/tools',
    '/monitoring',
    '/blockviewer',
    '/admin',
    '/buildproof',
  ]

  const requiresAuth = protectedPrefixes.some((p) => pathname === p || pathname.startsWith(p + '/'))

  // Routing rules:
  // - If unauth and /app/* => redirect /login
  // - If auth and /login or /register => redirect /app/chat
  // If we cannot confirm auth, fail closed.
  try {
    const meUrl = new URL('/api/me', requestOrigin)
    const resp = await fetch(meUrl, {
      headers: {
        cookie: req.headers.get('cookie') || '',
      },
      cache: 'no-store',
    })

    if (!resp.ok) {
      if (requiresAuth) {
        url.pathname = '/login'
        url.search = ''
        return NextResponse.redirect(url)
      }
      return NextResponse.next()
    }

    const data = (await resp.json()) as { auth?: boolean }
    const authed = Boolean(data?.auth)

    if (isAuthPage) {
      if (authed) {
        url.pathname = '/app/chat'
        url.search = ''
        return NextResponse.redirect(url)
      }
      return NextResponse.next()
    }

    if (requiresAuth) {
      if (!authed) {
        url.pathname = '/login'
        url.search = ''
        return NextResponse.redirect(url)
      }
    }

    // Compatibility: allow direct-to-frontend /app/* URLs even though the
    // Next.js route structure is /chat, /dashboard, ... (route groups).
    // We keep the browser URL as /app/* but internally serve the stripped route.
    if (isAppPrefixed && pathname.startsWith('/app/')) {
      url.pathname = pathname.slice('/app'.length) || '/'
      return NextResponse.rewrite(url)
    }

    return NextResponse.next()
  } catch {
    if (requiresAuth) {
      url.pathname = '/login'
      url.search = ''
      return NextResponse.redirect(url)
    }
    return NextResponse.next()
  }
}
