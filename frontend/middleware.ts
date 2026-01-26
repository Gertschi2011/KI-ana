import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export const config = {
  matcher: [
    // External (nginx) path
    '/app/:path*',
    // Internal Next.js paths (nginx may strip /app)
    '/chat',
    '/dashboard',
    '/settings',
    '/papa',
    '/blockviewer',
    '/monitoring',
    '/tools',
    '/admin/:path*',
    '/buildproof',
    // Public auth routes
    '/login',
    '/register',
  ],
}

export async function middleware(req: NextRequest) {
  const url = req.nextUrl.clone()
  const pathname = url.pathname || '/'

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

  const requiresAuth =
    (pathname.startsWith('/app/') && !isAuthPage) ||
    pathname === '/chat' ||
    pathname.startsWith('/chat/') ||
    pathname === '/dashboard' ||
    pathname.startsWith('/dashboard/') ||
    pathname === '/settings' ||
    pathname.startsWith('/settings/') ||
    pathname === '/papa' ||
    pathname.startsWith('/papa/') ||
    pathname === '/blockviewer' ||
    pathname.startsWith('/blockviewer/') ||
    pathname === '/monitoring' ||
    pathname.startsWith('/monitoring/') ||
    pathname === '/tools' ||
    pathname.startsWith('/tools/') ||
    pathname.startsWith('/admin/') ||
    pathname === '/buildproof'

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
