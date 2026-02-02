// MealMoment Service Worker - GitHub Pages Version
const CACHE_NAME = 'mealmoment-v4';
const APP_VERSION = '4.0';

// Files to cache
const CORE_FILES = [
  '/',
  '/index.html',
  '/owner-dashboard.html',
  '/install.html',
  '/manifest-customer.json',
  '/manifest-owner.json',
  '/firebase-config.js',
  '/sw.js',
  '/icon-192.png',
  '/icon-512.png',
  '/image/MealMomenetlogo.jpeg'
];

// External resources to cache
const EXTERNAL_RESOURCES = [
  'https://fonts.googleapis.com/css2?family=Poppins:wght@400;500;600;700;800&family=Inter:wght@300;400;500;600&display=swap',
  'https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css'
];

// Install - Cache files
self.addEventListener('install', event => {
  console.log('📱 Service Worker: Installing...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('📦 Caching core files');
        return cache.addAll(CORE_FILES);
      })
      .then(() => {
        console.log('✅ Installation complete');
        return self.skipWaiting();
      })
      .catch(error => {
        console.error('❌ Installation failed:', error);
      })
  );
});

// Activate - Clean up old caches
self.addEventListener('activate', event => {
  console.log('🚀 Service Worker: Activating...');
  
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheName !== CACHE_NAME) {
            console.log('🗑️ Deleting old cache:', cacheName);
            return caches.delete(cacheName);
          }
        })
      );
    })
    .then(() => {
      console.log('✅ Activation complete');
      return self.clients.claim();
    })
  );
});

// Fetch - Handle requests
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  
  // Skip non-GET requests
  if (event.request.method !== 'GET') return;
  
  // Handle navigation requests (HTML pages)
  if (event.request.mode === 'navigate') {
    event.respondWith(
      caches.match('/index.html')
        .then(cached => {
          if (cached) {
            return cached;
          }
          return fetch(event.request)
            .then(response => {
              const responseClone = response.clone();
              caches.open(CACHE_NAME)
                .then(cache => cache.put(event.request, responseClone));
              return response;
            })
            .catch(() => {
              // Return a simple offline page
              return new Response(`
                <!DOCTYPE html>
                <html>
                  <head>
                    <title>MealMoment - Offline</title>
                    <style>
                      body { font-family: Arial, sans-serif; padding: 20px; text-align: center; }
                      h1 { color: #2E7D32; }
                    </style>
                  </head>
                  <body>
                    <h1>🍽️ MealMoment</h1>
                    <p>You're offline right now.</p>
                    <p>The app will work when you're back online.</p>
                    <button onclick="location.reload()">Retry</button>
                  </body>
                </html>
              `, { headers: { 'Content-Type': 'text/html' } });
            });
        })
    );
    return;
  }
  
  // For other requests, try cache first
  event.respondWith(
    caches.match(event.request)
      .then(cachedResponse => {
        // Return cached response if found
        if (cachedResponse) {
          return cachedResponse;
        }
        
        // Otherwise fetch from network
        return fetch(event.request)
          .then(response => {
            // Don't cache if not a valid response
            if (!response || response.status !== 200 || response.type !== 'basic') {
              return response;
            }
            
            // Cache the response
            const responseToCache = response.clone();
            caches.open(CACHE_NAME)
              .then(cache => {
                cache.put(event.request, responseToCache);
              });
            
            return response;
          })
          .catch(() => {
            // If it's an image, return fallback
            if (event.request.url.match(/\.(jpg|jpeg|png|gif)$/i)) {
              return caches.match('/icon-192.png');
            }
            
            // Return offline message for other resources
            return new Response('Offline');
          });
      })
  );
});

// Background sync for offline orders
self.addEventListener('sync', event => {
  console.log('🔄 Background sync:', event.tag);
  
  if (event.tag === 'sync-orders') {
    event.waitUntil(syncOrders());
  }
});

async function syncOrders() {
  // This would sync any pending orders when back online
  console.log('Syncing pending orders...');
}
