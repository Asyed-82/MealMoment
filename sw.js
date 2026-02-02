// MealMoment Service Worker - sw.js
const CACHE_NAME = 'mealmoment-v1';
const APP_VERSION = 'v1.0';

// Files to cache for offline use
const urlsToCache = [
  './',                          // Root page
  './index.html',                // Customer app
  './owner-dashboard.html',      // Owner dashboard
  './install.html',              // Install page
  './sw.js',                     // This service worker
  './manifest-customer.json',    // Customer manifest
  './manifest-owner.json',       // Owner manifest
  './icon-192.png',              // App icon
  './icon-512.png',              // App icon
  './firebase-config.js',        // Firebase config
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css',
  'https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&family=Inter:wght@300;400;500;600&display=swap'
];

// Install service worker - cache all important files
self.addEventListener('install', event => {
  console.log('[Service Worker] Installing MealMoment app version', APP_VERSION);
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('[Service Worker] Caching app files');
        return cache.addAll(urlsToCache).catch(error => {
          console.log('[Service Worker] Cache addAll failed:', error);
        });
      })
      .then(() => {
        console.log('[Service Worker] Installation complete');
        return self.skipWaiting(); // Activate immediately
      })
  );
});

// Activate service worker - clean up old caches
self.addEventListener('activate', event => {
  console.log('[Service Worker] Activating new version');
  
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          // Delete old caches that aren't current
          if (cacheName !== CACHE_NAME) {
            console.log('[Service Worker] Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
    .then(() => {
      console.log('[Service Worker] Claiming clients');
      return self.clients.claim();
    })
  );
});

// Intercept network requests
self.addEventListener('fetch', event => {
  // Skip cross-origin requests
  if (!event.request.url.startsWith(self.location.origin) && 
      !event.request.url.includes('cdnjs.cloudflare.com') &&
      !event.request.url.includes('fonts.googleapis.com') &&
      !event.request.url.includes('fonts.gstatic.com')) {
    return;
  }
  
  event.respondWith(
    caches.match(event.request)
      .then(cachedResponse => {
        // If found in cache, return it
        if (cachedResponse) {
          console.log('[Service Worker] Serving from cache:', event.request.url);
          return cachedResponse;
        }
        
        // Otherwise fetch from network
        console.log('[Service Worker] Fetching from network:', event.request.url);
        return fetch(event.request)
          .then(networkResponse => {
            // Don't cache if not a valid response
            if (!networkResponse || networkResponse.status !== 200) {
              return networkResponse;
            }
            
            // Clone the response to cache it
            const responseToCache = networkResponse.clone();
            
            caches.open(CACHE_NAME)
              .then(cache => {
                cache.put(event.request, responseToCache);
                console.log('[Service Worker] Cached new resource:', event.request.url);
              });
              
            return networkResponse;
          })
          .catch(error => {
            console.log('[Service Worker] Network request failed:', error);
            
            // If it's an HTML request and we're offline, show the root page
            if (event.request.headers.get('accept').includes('text/html')) {
              return caches.match('./index.html');
            }
            
            // For other requests, return a fallback
            return new Response('You are offline. Please check your internet connection.', {
              status: 503,
              statusText: 'Service Unavailable',
              headers: new Headers({
                'Content-Type': 'text/plain'
              })
            });
          });
      })
  );
});

// Handle push notifications (for future use)
self.addEventListener('push', event => {
  console.log('[Service Worker] Push received:', event);
  
  const title = 'MealMoment';
  const options = {
    body: 'New order received!',
    icon: './icon-192.png',
    badge: './icon-192.png'
  };
  
  event.waitUntil(
    self.registration.showNotification(title, options)
  );
});

// Handle notification click
self.addEventListener('notificationclick', event => {
  console.log('[Service Worker] Notification clicked:', event);
  event.notification.close();
  
  event.waitUntil(
    clients.matchAll({ type: 'window' })
      .then(clientList => {
        // If a window is already open, focus it
        for (const client of clientList) {
          if (client.url === '/' && 'focus' in client) {
            return client.focus();
          }
        }
        
        // Otherwise open a new window
        if (clients.openWindow) {
          return clients.openWindow('./');
        }
      })
  );
});
