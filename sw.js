// MealMoment Service Worker - sw.js
const CACHE_NAME = 'mealmoment-v1';

// Files to cache
const urlsToCache = [
  '/',
  'index.html',
  'owner-dashboard.html',
  'image/MealMomenetlogo.jpeg',
  'manifest-customer.json',
  'manifest-owner.json'
];

// Install service worker
self.addEventListener('install', event => {
  console.log('Installing MealMoment app...');
  
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then(cache => {
        console.log('Caching app files');
        return cache.addAll(urlsToCache);
      })
  );
});

// Serve cached content when offline
self.addEventListener('fetch', event => {
  event.respondWith(
    caches.match(event.request)
      .then(response => {
        // Return cache if found
        if (response) {
          return response;
        }
        
        // Otherwise fetch from network
        return fetch(event.request)
          .then(response => {
            // Don't cache if not a valid response
            if(!response || response.status !== 200) {
              return response;
            }
            
            // Cache the new response
            const responseToCache = response.clone();
            caches.open(CACHE_NAME)
              .then(cache => {
                cache.put(event.request, responseToCache);
              });
              
            return response;
          })
          .catch(() => {
            // If network fails and no cache, show offline page
            return caches.match('/');
          });
      })
  );
});

// Clean up old caches
self.addEventListener('activate', event => {
  const cacheWhitelist = [CACHE_NAME];
  
  event.waitUntil(
    caches.keys().then(cacheNames => {
      return Promise.all(
        cacheNames.map(cacheName => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
});
