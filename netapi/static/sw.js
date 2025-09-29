const CACHE_NAME = 'kiana-pwa-v5';
const ASSETS = [
  '/static/blocks.html',
  '/static/blocks.js',
  '/static/papa_tools.html',
  '/static/styles.css',
  '/static/nav.html',
  '/static/nav.js',
  '/static/manifest.json',
  // Icons for PWA/homescreen
  '/static/favicon.svg',
  '/static/favicon.ico',
  '/static/apple-touch-icon.png',
  '/static/apple-touch-icon-precomposed.png',
  '/static/img/icon-192.png',
  '/static/img/icon-512.png',
  // Fonts
  '/static/fonts/Inter-roman.var.woff2',
  '/static/fonts/Inter-italic.var.woff2'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => cache.addAll(ASSETS)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then(keys => Promise.all(keys.map(k => k === CACHE_NAME ? Promise.resolve() : caches.delete(k)))).then(() => self.clients.claim())
  );
});

function isStaticAsset(url){
  return url.origin === location.origin && (url.pathname.startsWith('/static/') || url.pathname === '/');
}

function isApiCacheable(url){
  // cache GET queries for memory/blocks browsing for offline fallback
  if (url.origin !== location.origin) return false;
  if (url.pathname === '/api/memory/search') return true;
  if (url.pathname === '/blocks') return true;
  return false;
}

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  if (req.method !== 'GET') return; // only cache GET

  // Always bypass cache if a cache-busting query param is present
  if (url.search && /(?:\?|&)v=/.test(url.search)){
    event.respondWith(fetch(req));
    return;
  }

  if (isStaticAsset(url)){
    // For critical chat assets use network-first
    if (url.pathname === '/static/chat.html' || url.pathname === '/static/chat.js' || url.pathname === '/static/chat.css'){
      event.respondWith((async () => {
        try{ const resp = await fetch(req); return resp; }catch{
          const cache = await caches.open(CACHE_NAME);
          const cached = await cache.match(req);
          return cached || new Response('Offline', { status: 503, statusText: 'Offline' });
        }
      })());
      return;
    }
    // stale-while-revalidate for other static
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      const cached = await cache.match(req);
      const net = fetch(req).then(resp => { cache.put(req, resp.clone()); return resp; }).catch(() => null);
      return cached || (await net) || new Response('Offline', { status: 503, statusText: 'Offline' });
    })());
    return;
  }

  if (isApiCacheable(url)){
    // network-first with cache fallback for API listings
    event.respondWith((async () => {
      const cache = await caches.open(CACHE_NAME);
      try{
        const resp = await fetch(req);
        if (resp && resp.ok) cache.put(req, resp.clone());
        return resp;
      }catch{
        const cached = await cache.match(req);
        return cached || new Response(JSON.stringify({ ok:false, offline:true, items:[] }), { status: 200, headers: { 'Content-Type': 'application/json' } });
      }
    })());
    return;
  }
});
