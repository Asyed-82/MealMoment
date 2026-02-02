// MealMoment Service Worker - Fixed for GitHub Pages PWA
const CACHE_NAME = 'mealmoment-fixed-v2';
const APP_VERSION = '2.0';

// All paths MUST be relative for GitHub Pages
const CORE_FILES = [
  './',                    // Root - MOST IMPORTANT!
  './index.html',
  './owner-dashboard.html',
  './install.html',
  './manifest-customer.json',
  './manifest-owner.json',
  './firebase-config.js',
  './sw.js',
  './icon-192.png',
  './icon-512.png'
];

// EXTRA IMPORTANT: This intercepts ALL fetch requests
self.addEventListener('fetch', event => {
  // Skip non-GET requests
  if (event.request.method !== 'GET') return;
  
  const requestUrl = new URL(event.request.url);
  
  console.log('🔍 SW: Fetching', requestUrl.pathname);
  
  // For navigation requests, always serve index.html
  if (event.request.mode === 'navigate') {
    console.log('📍 SW: Navigation request detected');
    event.respondWith(
      caches.match('./index.html')
        .then(response => {
          if (response) {
            console.log('✅ SW: Serving index.html from cache');
            return response;
          }
          console.log('⚠️ SW: Fetching index.html from network');
          return fetch('./index.html');
        })
        .catch(error => {
          console.error('❌ SW: Error serving index.html:', error);
          return new Response(`
            <!DOCTYPE html>
            <html>
              <head><title>MealMoment</title></head>
              <body style="font-family: Arial; text-align: center; padding: 50px;">
                <h1>🍽️ MealMoment</h1>
                <p>App loading...</p>
                <script>
                  setTimeout(() => {
                    window.location.href = './index.html';
                  }, 1000);
                </script>
              </body>
            </html>
          `, { headers: { 'Content-Type': 'text/html' } });
        })
    );
    return;
  }
  
  // For other requests, try cache then network
  event.respondWith(
    caches.match(event.request)
      .then(cached => {
        if (cached) {
          console.log('✅ SW: Serving from cache');
          return cached;
        }
        
        console.log('🌐 SW: Fetching from network');
        return fetch(event.request)
          .then(response => {
            // Only cache successful responses
            if (response && response.status === 200) {
              const clone = response.clone();
              caches.open(CACHE_NAME)
                .then(cache => cache.put(event.request, clone));
            }
            return response;
          })
          .catch(() => {
            // If fetch fails and it's an HTML request, serve index.html
            if (event.request.headers.get('accept')?.includes('text/html')) {
              return caches.match('./index.html');
            }
            return new Response('Offline');
          });
      })
  );
});

// Install - Cache all core files
self.addEventListener('install', event => {
  console.log('🔄 SW: Installing version', APP_VERSION);
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('📦 SW: Caching core files');
        return cache.addAll(CORE_FILES);
      })
      .then(() => {
        console.log('✅ SW: Installation complete');
        return self.skipWaiting(); // Activate immediately
      })
      .catch(error => {
        console.error('❌ SW: Cache error:', error);
      })
  );
});

// Activate - Clean up old caches
self.addEventListener('activate', event => {
  console.log('🚀 SW: Activating');
  
  event.waitUntil(
    caches.keys().then(keys => {
      return Promise.all(
        keys.map(key => {
          if (key !== CACHE_NAME) {
            console.log('🗑️ SW: Deleting old cache:', key);
            return caches.delete(key);
          }
        })
      );
    })
    .then(() => {
      console.log('✅ SW: Activation complete');
      return self.clients.claim(); // Take control immediately
    })
  );
});
