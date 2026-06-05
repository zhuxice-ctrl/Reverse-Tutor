/**
 * Reverse Tutor mobile service worker.
 * App shell is network-first so APK/PWA upgrades cannot keep serving stale index.html.
 */
const VERSION = 'rt-mobile-v0.19.4-43-auto-multimodal-cache';
const SHELL = [
  './manifest.json',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(VERSION)
      .then((cache) => cache.addAll(SHELL))
      .then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(
        keys.filter((key) => key !== VERSION && /^rt-mobile-/.test(key))
          .map((key) => caches.delete(key))
      ))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('message', (e) => {
  if (e.data && e.data.type === 'SKIP_WAITING') self.skipWaiting();
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;
  if (e.request.method !== 'GET') return;

  const isAppShell = e.request.mode === 'navigate'
    || url.pathname.endsWith('/')
    || url.pathname.endsWith('/index.html')
    || url.pathname.endsWith('/app/')
    || url.pathname.endsWith('/app/index.html');

  if (url.pathname.endsWith('/latest.json')) {
    e.respondWith(fetch(e.request, { cache: 'no-store' }));
    return;
  }

  if (isAppShell) {
    e.respondWith(
      fetch(e.request, { cache: 'no-store' }).then((res) => {
        if (res.ok) {
          const clone = res.clone();
          caches.open(VERSION).then((cache) => cache.put('./index.html', clone));
        }
        return res;
      }).catch(() => caches.match('./index.html').then((cached) => cached || caches.match(e.request)))
    );
    return;
  }

  e.respondWith(
    caches.match(e.request).then((cached) => {
      if (cached) return cached;
      return fetch(e.request).then((res) => {
        if (res.ok) {
          const clone = res.clone();
          caches.open(VERSION).then((cache) => cache.put(e.request, clone));
        }
        return res;
      }).catch(() => cached);
    })
  );
});
