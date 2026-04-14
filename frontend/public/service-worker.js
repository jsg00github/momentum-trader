const CACHE_NAME = 'momentum-v2';
const STATIC_ASSETS = ['/', '/index.html'];

self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => cache.addAll(STATIC_ASSETS))
    );
    self.skipWaiting();
});

self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        )
    );
});

self.addEventListener('fetch', event => {
    // Only cache GET requests
    if (event.request.method !== 'GET') return;
    
    // Never cache API calls to ensure fresh data
    if (event.request.url.includes('/api/') || event.request.url.includes('/argentina/')) {
        return;
    }
    
    event.respondWith(
        caches.match(event.request).then(cached => cached || fetch(event.request))
    );
});
