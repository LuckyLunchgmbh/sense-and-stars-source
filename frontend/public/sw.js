/* Public app shell only. API responses and client records never enter Cache Storage. */
const CACHE = "sense-stars-public-v1.4.1";
const PUBLIC_FILES = [
  "/",
  "/index.html",
  "/icon.svg",
  "/icon-192.png",
  "/icon-512.png",
  "/icon-maskable-512.png",
  "/manifest.webmanifest",
];
self.addEventListener("install", (event) => {
  event.waitUntil(
    (async () => {
      const cache = await caches.open(CACHE);
      const response = await fetch("/index.html", { cache: "reload" });
      if (!response.ok) throw new Error("App shell unavailable");
      const html = await response.text();
      const assets = [
        ...html.matchAll(/(?:src|href)="(\/assets\/[^"]+)"/g),
      ].map((match) => match[1]);
      await cache.addAll([...PUBLIC_FILES, ...assets]);
    })(),
  );
  self.skipWaiting();
});
self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((keys) =>
        Promise.all(
          keys
            .filter(
              (key) =>
                (key.startsWith("soulflow-public-") ||
                  key.startsWith("sense-stars-public-")) &&
                key !== CACHE,
            )
            .map((key) => caches.delete(key)),
        ),
      )
      .then(() => self.clients.claim()),
  );
});
self.addEventListener("fetch", (event) => {
  const url = new URL(event.request.url);
  if (
    event.request.method !== "GET" ||
    url.origin !== self.location.origin ||
    url.pathname.startsWith("/api")
  )
    return;
  const isStatic =
    PUBLIC_FILES.includes(url.pathname) ||
    /^\/assets\/[\w.-]+\.(js|css|svg|png|webp|woff2?)$/.test(url.pathname);
  if (!isStatic) return;
  event.respondWith(
    fetch(event.request)
      .then((response) => {
        if (response.ok && response.type === "basic") {
          const copy = response.clone();
          caches.open(CACHE).then((cache) => cache.put(event.request, copy));
        }
        return response;
      })
      .catch(() =>
        caches
          .match(event.request)
          .then(
            (cached) =>
              cached ||
              (event.request.mode === "navigate"
                ? caches.match("/index.html")
                : Response.error()),
          ),
      ),
  );
});
