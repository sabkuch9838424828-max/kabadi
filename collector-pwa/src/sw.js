/* Service worker for the Collector PWA.
 *
 * - Precache + serve the app shell so the UI loads with no network.
 * - NetworkFirst caching for the price board / recycler directory.
 * - Background Sync queue: lots captured offline that fail to upload (e.g. the
 *   connection dropped mid-request) are retried automatically by the browser
 *   when connectivity returns, using workbox-background-sync.
 */
import { precacheAndRoute, cleanupOutdatedCaches } from 'workbox-precaching'
import { clientsClaim } from 'workbox-core'
import { registerRoute, NavigationRoute } from 'workbox-routing'
import { NetworkFirst } from 'workbox-strategies'
import { ExpirationPlugin } from 'workbox-expiration'
import { BackgroundSyncPlugin } from 'workbox-background-sync'

// Take control of open pages as soon as a new build is deployed, so a rebuilt
// bundle is never shadowed by the previous precache.
self.skipWaiting()
clientsClaim()

// eslint-disable-next-line no-undef
precacheAndRoute(self.__WB_MANIFEST)
cleanupOutdatedCaches()

// App shell navigation fallback so deep links work offline.
registerRoute(
  new NavigationRoute(
    async ({ event }) => {
      const cache = await caches.open('workbox-precache-v2')
      const cached = await cache.match('/index.html')
      return cached || fetch(event.request)
    },
    { denylist: [/^\/api\//] }
  )
)

const offlineQueue = new BackgroundSyncPlugin('kc-sync-lots', {
  maxRetentionTime: 24 * 60
})

// Offline lot sync: retried by the browser until it succeeds.
// A single NetworkFirst route with the BackgroundSyncPlugin handles both the
// live request and the queued retry; registering a plain route first would
// shadow this one and disable background sync.
registerRoute(
  ({ url, request }) => url.pathname === '/api/v1/lots/sync' && request.method === 'POST',
  // eslint-disable-next-line no-undef
  new NetworkFirst({ plugins: [offlineQueue] }),
  'POST'
)

registerRoute(
  ({ url }) => url.pathname.startsWith('/api/v1/prices') || url.pathname.startsWith('/api/v1/recyclers') || url.pathname.startsWith('/api/v1/ml/'),
  new NetworkFirst({
    cacheName: 'kc-api-cache',
    networkTimeoutSeconds: 4,
    plugins: [new ExpirationPlugin({ maxEntries: 128, maxAgeSeconds: 60 * 60 * 24 * 7 })]
  })
)

// eslint-disable-next-line no-undef
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    // eslint-disable-next-line no-undef
    self.skipWaiting()
  }
})
