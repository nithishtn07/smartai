/**
 * =============================================================================
 * CampusGuard AI — PWA Registration & Web Push Manager
 * =============================================================================
 */

(function () {
  'use strict';

  // 1. Register Service Worker
  if ('serviceWorker' in navigator) {
    window.addEventListener('load', () => {
      navigator.serviceWorker
        .register('/static/sw.js')
        .then((reg) => {
          console.log('[CampusGuard PWA] Service Worker registered with scope:', reg.scope);
        })
        .catch((err) => {
          console.warn('[CampusGuard PWA] Service Worker registration failed:', err);
        });
    });
  }

  // 2. Install Prompt Interception
  let deferredPrompt = null;

  window.addEventListener('beforeinstallprompt', (e) => {
    e.preventDefault();
    deferredPrompt = e;

    // Show custom subtle install button if container exists
    const installBtn = document.getElementById('pwa-install-btn');
    if (installBtn) {
      installBtn.style.display = 'inline-flex';
      installBtn.addEventListener('click', async () => {
        if (deferredPrompt) {
          deferredPrompt.prompt();
          const { outcome } = await deferredPrompt.userChoice;
          console.log('[CampusGuard PWA] Install outcome:', outcome);
          deferredPrompt = null;
          installBtn.style.display = 'none';
        }
      });
    }
  });

  // 3. Web Push Notification Permission Request
  window.requestCampusPushNotifications = async function () {
    if (!('Notification' in window)) {
      alert('This browser does not support desktop/mobile push notifications.');
      return false;
    }

    if (Notification.permission === 'granted') {
      return true;
    }

    if (Notification.permission !== 'denied') {
      const permission = await Notification.requestPermission();
      if (permission === 'granted') {
        new Notification('🛡️ CampusGuard Safety Alerts Enabled', {
          body: 'You will now receive high-priority SOS emergency notices directly on your device.',
          icon: '/static/icons/icon-192.png'
        });
        return true;
      }
    }
    return false;
  };
})();
