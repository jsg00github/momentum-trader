// Momentum Trader Service Worker - MINIMAL MODE
// Disabled aggressive caching to ensure fresh data loads

const CACHE_VERSION = 'v39-nocache';

// Install - skip caching entirely
self.addEventListener('install', event => {
    console.log('[SW] Installing (no-cache mode)...');
    self.skipWaiting();
});

// Activate - clear ALL caches
self.addEventListener('activate', event => {
    console.log('[SW] Activating (clearing all caches)...');
    event.waitUntil(
        caches.keys().then(cacheNames => {
            return Promise.all(
                cacheNames.map(name => {
                    console.log('[SW] Deleting cache:', name);
                    return caches.delete(name);
                })
            );
        }).then(() => self.clients.claim())
    );
});

// Fetch - ALWAYS use network (no caching)
self.addEventListener('fetch', event => {
    // Just pass through to network, no caching
    event.respondWith(
        fetch(event.request, {
            cache: 'no-store'
        }).catch(err => {
            console.error('[SW] Fetch failed:', err);
            return new Response('Network error', { status: 503 });
        })
    );
});

console.log('[SW] Service Worker loaded (no-cache mode)');
