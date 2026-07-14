// Service worker — NETWORK-FIRST so the installed home-screen app always shows the latest
// (code + data) when online, and falls back to cache only when offline. This fixes the
// "PWA stuck on old version" problem caused by cache-first shells.
const CACHE = "sma-v12";
const SHELL = ["./", "index.html", "app.js", "manifest.webmanifest", "icon-192.png", "icon-512.png",
  "bronco.html", "bronco.js", "bronco.json"];

self.addEventListener("install", e => {
  // Pre-cache the shell for offline, then take over immediately (no waiting for old tabs to close).
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", e => {
  // Drop every old cache version, then claim open clients so the new worker controls them now.
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", e => {
  if (e.request.method !== "GET") return;
  e.respondWith((async () => {
    try {
      // Network-first: always try the live version (with a short timeout so a slow network
      // doesn't hang the app), and refresh the cache copy for offline use.
      const net = await fetch(e.request);
      if (net && (net.ok || net.type === "opaque")) {
        const copy = net.clone();
        caches.open(CACHE).then(c => c.put(e.request, copy)).catch(() => {});
      }
      return net;
    } catch (_) {
      // Offline → serve from cache; for navigations, fall back to the cached shell.
      const cached = await caches.match(e.request);
      return cached || (e.request.mode === "navigate" ? caches.match("index.html") : Response.error());
    }
  })());
});
