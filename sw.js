// MealMoment Service Worker - GitHub Pages Version
const CACHE_NAME = 'mealmoment-gh-v3';
const APP_VERSION = '3.0';
const BASE_PATH = '/MealMoment/'; // <-- IMPORTANT: Your GitHub Pages path

// Files to cache with GitHub Pages path
const CORE_FILES = [
  '/MealMoment/',
  '/MealMoment/index.html',
  '/MealMoment/owner-dashboard.html',
  '/MealMoment/install.html',
  '/MealMoment/manifest-customer.json',
  '/MealMoment/manifest-owner.json',
  '/MealMoment/firebase-config.js',
  '/MealMoment/sw.js',
  '/MealMoment/icon-192.png',
  '/MealMoment/icon-512.png'
];

// Install - Cache files
self.addEventListener('install', event => {
  console.log('📱 SW: Installing for GitHub Pages');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('📦 SW: Caching GitHub Pages files');
        return cache.addAll(CORE_FILES);
      })
      .then(() => {
        console.log('✅ SW: Installation complete');
        return self.skipWaiting();
      })
  );
});

// Activate - Clean up
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
      return self.clients.claim();
    })
  );
});

// Fetch - Handle requests
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  
  // Skip non-GET requests
  if (event.request.method !== 'GET') return;
  
  // Handle navigation requests (when PWA opens)
  if (event.request.mode === 'navigate') {
    console.log('📍 SW: Handling navigation request to:', url.pathname);
    
    event.respondWith(
      caches.match('/MealMoment/index.html')
        .then(cached => {
          if (cached) {
            console.log('✅ SW: Serving index.html from cache');
            return cached;
          }
          console.log('🌐 SW: Fetching index.html from network');
          return fetch('/MealMoment/index.html');
        })
        .catch(error => {
          console.error('❌ SW: Error:', error);
          return new Response(`
            <!DOCTYPE html>
            <html>
              <head>
                <title>MealMoment - Loading</title>
                <meta http-equiv="refresh" content="0; url=https://asyed-82.github.io/MealMoment/">
              </head>
              <body>
                <p>Redirecting to MealMoment...</p>
              </body>
            </html>
          `, { headers: { 'Content-Type': 'text/html' } });
        })
    );
    return;
  }
  
  // For other requests
  event.respondWith(
    caches.match(event.request)
      .then(cached => {
        if (cached) {
          return cached;
        }
        
        return fetch(event.request)
          .then(response => {
            // Cache successful responses
            if (response && response.status === 200) {
              const clone = response.clone();
              caches.open(CACHE_NAME)
                .then(cache => cache.put(event.request, clone));
            }
            return response;
          })
          .catch(() => {
            // If offline and it's an image, return a fallback
            if (url.pathname.includes('.png') || url.pathname.includes('.jpg')) {
              return caches.match('/MealMoment/icon-192.png');
            }
            return new Response('Offline');
          });
      })
  );
});
