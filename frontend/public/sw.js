// Boond service worker: shows the morning advice notification and opens the
// field page when it is tapped. It does not cache pages.
self.addEventListener('push', (event) => {
  const data = event.data ? event.data.json() : {}
  event.waitUntil(
    self.registration.showNotification(data.title || 'Boond', {
      body: data.body || '',
      icon: '/icon-192.png',
      badge: '/icon-192.png',
      lang: 'hi',
      data: { url: data.url || '/' },
    }),
  )
})

// Take control of open pages at once. Without this, the tab that registered the
// worker stays uncontrolled until it reloads, and navigate() on it rejects.
self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const target = new URL(event.notification.data.url, self.location.origin).href
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true }).then(async (windows) => {
      const open = windows.find((w) => w.url.startsWith(self.location.origin))
      if (open) {
        try {
          const navigated = await open.navigate(target)
          if (navigated) return navigated.focus()
        } catch {
          /* not controlled by this worker: open a new window instead */
        }
      }
      return self.clients.openWindow(target)
    }),
  )
})
