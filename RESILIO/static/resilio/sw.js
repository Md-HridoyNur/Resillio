/* Explicit static allowlist only: no authenticated pages or API responses. */
const VERSION = "resilio-assets-v2";
const ASSETS = [
  "/static/resilio/offline.html",
  "/static/resilio/app.css",
  "/static/resilio/app.js",
  "/static/resilio/network.js",
  "/static/resilio/theme.js",
  "/static/resilio/fonts/display.ttf",
  "/static/resilio/fonts/ui.ttf",
];
self.addEventListener("install", (event) =>
  event.waitUntil(
    caches
      .open(VERSION)
      .then((cache) => cache.addAll(ASSETS))
      .then(() => self.skipWaiting()),
  ),
);
self.addEventListener("activate", (event) =>
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter((k) => k.startsWith("resilio-assets-") && k !== VERSION)
            .map((k) => caches.delete(k)),
        ),
      )
      .then(() => self.clients.claim()),
  ),
);
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin || event.request.method !== "GET")
    return;
  if (ASSETS.includes(url.pathname)) {
    event.respondWith(
      caches
        .match(url.pathname)
        .then((cached) => cached || fetch(event.request)),
    );
    return;
  }
  if (event.request.mode === "navigate" && url.pathname === "/") {
    event.respondWith(
      fetch(event.request).catch(() =>
        caches.match("/static/resilio/offline.html"),
      ),
    );
  }
});
