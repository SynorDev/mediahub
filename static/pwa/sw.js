const CACHE_NAME = 'mediahub-desktop-pwa-v1';
const PRECACHE_ASSETS = [
  '/',
  '/manifest.json',
  '/static/pwa/icon.svg',
  '/static/pwa/icon-192.png',
  '/static/pwa/icon-512.png',
  '/offline'
];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_ASSETS).catch(err => {
        console.warn('[PWA SW] Precache assets warning:', err);
      });
    }).then(() => self.skipWaiting())
  );
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.map((k) => {
          if (k !== CACHE_NAME) {
            return caches.delete(k);
          }
        })
      );
    }).then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // No interceptar conexiones WebSocket ni peticiones POST/PUT/DELETE
  if (req.method !== 'GET' || url.protocol.startsWith('ws') || url.pathname.includes('_nicegui_ws') || url.pathname.includes('socket.io')) {
    return;
  }

  // Para assets estáticos precacheados (iconos, manifest)
  if (url.pathname.startsWith('/static/pwa') || url.pathname === '/manifest.json') {
    event.respondWith(
      caches.match(req).then((cached) => cached || fetch(req))
    );
    return;
  }

  // Para navegación principal: Network first, con fallback a offline si no hay red
  if (req.mode === 'navigate') {
    event.respondWith(
      fetch(req).catch(() => {
        return caches.match('/offline') || caches.match('/');
      })
    );
    return;
  }

  // Default: Network with cache fallback
  event.respondWith(
    fetch(req).catch(() => caches.match(req))
  );
});
