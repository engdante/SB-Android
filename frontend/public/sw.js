/**
 * pi_sb — Second Brain
 * Service Worker за PWA функционалност.
 * 
 * Стратегия: Cache-First за статиката, Network-First за API заявките.
 */

const CACHE_NAME = 'pi_sb-v1';

// Ресурси за pre-cache (кеширани още при инсталация)
const PRECACHE_URLS = [
  '/',
  '/index.html',
];

// Инсталиране на service worker
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      return cache.addAll(PRECACHE_URLS);
    })
  );
  // Активираме веднага, без да чакаме затваряне на страницата
  self.skipWaiting();
});

// Активиране — изчистваме стари кешове
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames
          .filter((name) => name !== CACHE_NAME)
          .map((name) => caches.delete(name))
      );
    })
  );
  // Веднага взимаме контрол над всички клиенти
  self.clients.claim();
});

// Стратегия за кеширане
self.addEventListener('fetch', (event) => {
  const request = event.request;
  const url = new URL(request.url);

  // API заявки — Network First (винаги актуални данни)
  if (url.pathname.startsWith('/api/')) {
    event.respondWith(networkFirst(request));
    return;
  }

  // Статични ресурси (JS, CSS, икони) — Cache First
  if (
    request.destination === 'script' ||
    request.destination === 'style' ||
    request.destination === 'font' ||
    request.destination === 'image' ||
    url.pathname.startsWith('/assets/')
  ) {
    event.respondWith(cacheFirst(request));
    return;
  }

  // HTML навигация — Network First
  if (request.mode === 'navigate') {
    event.respondWith(networkFirst(request));
    return;
  }

  // Всичко останало — Network First
  event.respondWith(networkFirst(request));
});

/**
 * Cache First стратегия:
 * 1. Проверяваме кеша
 * 2. Ако има — връщаме от кеша
 * 3. Ако няма — мрежа + запис в кеша
 */
async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) {
    return cached;
  }
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    return new Response('Offline', { status: 503 });
  }
}

/**
 * Network First стратегия:
 * 1. Опитваме мрежа
 * 2. При успех — записваме в кеша и връщаме
 * 3. При грешка — връщаме от кеша (ако има)
 */
async function networkFirst(request) {
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch (error) {
    const cached = await caches.match(request);
    if (cached) {
      return cached;
    }
    return new Response('Offline', { status: 503 });
  }
}