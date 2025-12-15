// static/service-worker.js

const CACHE_NAME = 'canvas-tracker-cache-v2'; // Incremented version due to changes
const URLS_TO_CACHE = [
  '/', // The main page
  // Note: {{ url_for(...) }} won't work here. Provide static paths.
  // Assuming your static files are served from /static/
  '/static/style.css',
  '/static/script.js',
  '/static/manifest.json', // Cache the manifest
  // Add paths to your icons here if you want them cached immediately
  '/static/icons/icon-192x192.png', // Make sure this path is correct
  '/static/icons/icon-512x512.png', // Make sure this path is correct
  // External resources
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css',
  'https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js'
  // Add other critical assets if any
];

// Install event: Cache core assets
self.addEventListener('install', event => {
  console.log('Service Worker: Installing...');
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Service Worker: Caching app shell and core assets');
        // Use 'reload' to ensure fresh copies from network during install for external resources
        const cachePromises = URLS_TO_CACHE.map(urlToCache => {
            const request = new Request(urlToCache, {cache: 'reload'});
            return fetch(request).then(response => {
                if (!response.ok) {
                    // For external resources like CDNs, a failure might be temporary or due to CORS if not configured.
                    // For local assets, this would indicate a wrong path.
                    console.error(`Service Worker: Failed to fetch ${urlToCache} for caching. Status: ${response.status}`);
                    // Don't put bad responses into cache.
                    // Depending on strictness, you might throw an error here to fail the SW install
                    // or just log and continue, hoping for runtime caching.
                    // For now, just log.
                    return Promise.resolve(); // Resolve so other caching can continue
                }
                return cache.put(urlToCache, response);
            }).catch(error => {
                console.error(`Service Worker: Fetch error for ${urlToCache} during install:`, error);
            });
        });
        return Promise.all(cachePromises);
      })
      .then(() => {
        console.log('Service Worker: Installation complete, assets cached (or attempted).');
        return self.skipWaiting(); // Activate new service worker immediately
      })
      .catch(error => {
        console.error('Service Worker: Cache open or asset caching during installation failed:', error);
      })
  );
});

// Activate event: Clean up old caches
self.addEventListener('activate', event => {
  console.log('Service Worker: Activating...');
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('Service Worker: Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    }).then(() => {
        console.log('Service Worker: Activation complete, old caches cleaned. Now controlling client.');
        return self.clients.claim(); // Take control of any open clients
    })
  );
});

// Fetch event: Serve cached content when offline, or fetch from network
self.addEventListener('fetch', event => {
  // We only want to handle GET requests for caching
  if (event.request.method !== 'GET') {
    return;
  }

  // Network first, then cache for API calls (or specific paths)
  // This example is more generic: Cache first for assets, network for navigation
  if (event.request.url.includes('/api/')) {
    // For API calls, always try network first, then fallback to cache if appropriate (not typical for dynamic data)
    // Or simply, don't cache API calls by not handling them here / letting browser do its thing.
    // For this app, API calls fetch dynamic data, so usually, we don't want to serve stale API data from cache.
    // So, we can just let them pass through or implement a network-first strategy.
    // event.respondWith(fetch(event.request)); // Simplest: always network for API
    return; // Let browser handle API calls by default (no offline for API)
  }


  event.respondWith(
    caches.match(event.request)
      .then(cachedResponse => {
        // Cache hit - return response
        if (cachedResponse) {
          // console.log('Service Worker: Serving from cache:', event.request.url);
          return cachedResponse;
        }

        // Not in cache - fetch from network, then cache it
        // console.log('Service Worker: Fetching from network and caching:', event.request.url);
        return fetch(event.request).then(
          networkResponse => {
            // Check if we received a valid response
            if (!networkResponse || networkResponse.status !== 200 || networkResponse.type !== 'basic' && networkResponse.type !== 'cors') {
              // Don't cache opaque responses or errors for CDN assets, but return them.
              // For local assets, a non-200 means an issue.
              if (networkResponse.type === 'opaque') {
                  // console.log('Service Worker: Opaque response not cached but served:', event.request.url);
              } else {
                  // console.log('Service Worker: Bad network response, not caching:', event.request.url, networkResponse.status);
              }
              return networkResponse;
            }

            // IMPORTANT: Clone the response. A response is a stream
            // and because we want the browser to consume the response
            // as well as the cache consuming the response, we need
            // to clone it so we have two streams.
            const responseToCache = networkResponse.clone();

            caches.open(CACHE_NAME)
              .then(cache => {
                // console.log('Service Worker: Caching new resource:', event.request.url);
                cache.put(event.request, responseToCache);
              });

            return networkResponse;
          }
        ).catch(error => {
          console.error('Service Worker: Fetch failed; returning offline page or error for:', event.request.url, error);
          // If fetch fails (e.g., offline), you could return a fallback offline page
          // For example: return caches.match('/offline.html');
          // For now, just let the browser handle the error (which might show its default offline page)
        });
      })
  );
});


// --- Push Event Listener (Commented Out - Replaced by Discord) ---
/*
self.addEventListener('push', event => {
  console.log('[Service Worker] Push Received.');
  // ... (implementation was here)
});
*/

// --- Notification Click Event Listener (Commented Out - Replaced by Discord) ---
/*
self.addEventListener('notificationclick', event => {
  console.log('[Service Worker] Notification click Received.');
  // ... (implementation was here)
});
*/
