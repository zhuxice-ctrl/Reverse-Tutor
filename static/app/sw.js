/**
 * Reverse Tutor 移动端 Service Worker
 * 策略：
 *   - 应用壳（index.html、icon、manifest）走 cache-first，离线可用
 *   - LLM API 请求始终 network-only（不缓存）
 *   - 缓存版本随发布更新
 */
const VERSION = 'rt-mobile-v0.19.2-41-mobile-ui-patch';
const SHELL = [
  './',
  './index.html',
  './manifest.json',
  './icon-192.png',
  './icon-512.png',
  './icon-maskable.png',
];

self.addEventListener('install', (e) => {
  e.waitUntil(
    caches.open(VERSION).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (e) => {
  const url = new URL(e.request.url);
  if (url.origin !== self.location.origin) return;
  if (e.request.method !== 'GET') return;

  const isAppShell = e.request.mode === 'navigate'
    || url.pathname.endsWith('/app/')
    || url.pathname.endsWith('/app/index.html');

  if (url.pathname.endsWith('/app/latest.json')) {
    e.respondWith(fetch(e.request, { cache: 'no-store' }));
    return;
  }

  if (isAppShell) {
    e.respondWith(
      fetch(e.request).then((res) => {
        if (res.ok) {
          const clone = res.clone();
          caches.open(VERSION).then((c) => c.put('./index.html', clone));
        }
        return res;
      }).catch(() => caches.match(e.request).then((cached) => cached || caches.match('./index.html')))
    );
    return;
  }

  e.respondWith(
    caches.match(e.request).then((cached) => {
      if (cached) return cached;
      return fetch(e.request).then((res) => {
        if (res.ok) {
          const clone = res.clone();
          caches.open(VERSION).then((c) => c.put(e.request, clone));
        }
        return res;
      }).catch(() => cached);
    })
  );
});
