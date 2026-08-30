/**
 * =============================================================================
 * CampusGuard AI — Enterprise Progressive Web App (PWA) Service Worker
 * =============================================================================
 * Provides offline caching for Student Smart ID, Timetable, and Emergency Directory.
 * Handles background push notifications for critical SOS safety alerts.
 * =============================================================================
 */

const CACHE_NAME = 'campusguard-pwa-v1';
const STATIC_ASSETS = [
  '/',
  '/static/css/index.css',
  '/static/css/student-portal.css',
  '/static/css/parent.css',
  '/static/css/emergency.css',
  '/static/css/campusguard-toast.css',
  '/static/js/campusguard-realtime.js',
  '/static/js/student-portal.js',
  '/static/js/emergency.js',
  '/static/manifest.json'
];

// 1. Install Event: Pre-cache static shell
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME).then((cache) => {
      console.log('[CampusGuard SW] Pre-caching offline application shell.');
      return cache.addAll(STATIC_ASSETS).catch((err) => {
        console.warn('[CampusGuard SW] Pre-cache partial warning:', err);
      });
    })
  );
  self.skipWaiting();
});

// 2. Activate Event: Clean up stale caches
self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches.keys().then((keys) => {
      return Promise.all(
        keys.filter((key) => key !== CACHE_NAME).map((key) => caches.delete(key))
      );
    })
  );
  self.clients.claim();
});

// 3. Fetch Event: Network-First with Cache Fallback Strategy
self.addEventListener('fetch', (event) => {
  const req = event.request;
  const url = new URL(req.url);

  // Skip non-GET requests and WebSocket connections
  if (req.method !== 'GET' || url.protocol.startsWith('ws')) {
    return;
  }

  // Static assets: Cache-First
  if (url.pathname.startsWith('/static/')) {
    event.respondWith(
      caches.match(req).then((cachedResponse) => {
        if (cachedResponse) {
          return cachedResponse;
        }
        return fetch(req).then((networkResponse) => {
          if (networkResponse && networkResponse.status === 200) {
            const resClone = networkResponse.clone();
            caches.open(CACHE_NAME).then((cache) => cache.put(req, resClone));
          }
          return networkResponse;
        });
      })
    );
    return;
  }

  // Dynamic pages: Network-First with Cache Fallback
  event.respondWith(
    fetch(req)
      .then((networkResponse) => {
        if (networkResponse && networkResponse.status === 200) {
          const resClone = networkResponse.clone();
          caches.open(CACHE_NAME).then((cache) => cache.put(req, resClone));
        }
        return networkResponse;
      })
      .catch(() => {
        return caches.match(req).then((cachedResponse) => {
          if (cachedResponse) {
            return cachedResponse;
          }
          // Generic offline fallback response
          return new Response(
            `<!DOCTYPE html>
            <html lang="en">
            <head>
              <meta charset="UTF-8">
              <meta name="viewport" content="width=device-width, initial-scale=1.0">
              <title>CampusGuard — Offline Mode</title>
              <style>
                body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #0a0f1d; color: #f8fafc; display: flex; align-items: center; justify-content: center; min-height: 100vh; margin: 0; padding: 20px; text-align: center; }
                .card { background: #1e293b; border: 1px solid #334155; padding: 32px; border-radius: 16px; max-width: 480px; box-shadow: 0 20px 25px -5px rgba(0,0,0,0.5); }
                .icon { font-size: 48px; margin-bottom: 16px; }
                h1 { font-size: 24px; margin-bottom: 8px; color: #6366f1; }
                p { color: #94a3b8; font-size: 15px; line-height: 1.5; }
                .sos-box { background: #450a0a; border: 1px solid #ef4444; border-radius: 8px; padding: 16px; margin-top: 24px; }
                .sos-num { color: #f87171; font-weight: bold; font-size: 18px; text-decoration: none; display: block; margin-top: 8px; }
                .btn { display: inline-block; margin-top: 20px; background: #4f46e5; color: white; padding: 10px 20px; border-radius: 8px; text-decoration: none; font-weight: 600; }
              </style>
            </head>
            <body>
              <div class="card">
                <div class="icon">📡</div>
                <h1>CampusGuard Offline Mode</h1>
                <p>You are currently offline. Cached timetables and academic documents remain available from device storage.</p>
                <div class="sos-box">
                  <div style="color: #fca5a5; font-weight: 600;">🚨 DIRECT EMERGENCY HELPLINE (TELECOM)</div>
                  <a href="tel:+919123456780" class="sos-num">📞 +91 91234 56780 (Security 24/7)</a>
                  <a href="tel:112" class="sos-num">👮 112 (National Emergency)</a>
                </div>
                <a href="/" class="btn" onclick="window.location.reload();">Retry Connection</a>
              </div>
            </body>
            </html>`,
            { headers: { 'Content-Type': 'text/html; charset=utf-8' } }
          );
        });
      })
  );
});

// 4. Push Notification Event: Background emergency alerts
self.addEventListener('push', (event) => {
  let data = {};
  if (event.data) {
    try {
      data = event.data.json();
    } catch (e) {
      data = { title: 'CampusGuard Alert', body: event.data.text() };
    }
  }

  const title = data.title || 'CampusGuard Safety Notification';
  const options = {
    body: data.body || 'A new official campus update has been broadcast.',
    icon: '/static/icons/icon-192.png',
    badge: '/static/icons/icon-192.png',
    vibrate: [200, 100, 200, 100, 400],
    data: {
      url: data.url || '/'
    }
  };

  event.waitUntil(self.registration.showNotification(title, options));
});

// 5. Notification Click Event
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  const urlToOpen = event.notification.data ? event.notification.data.url : '/';
  event.waitUntil(clients.openWindow(urlToOpen));
});
