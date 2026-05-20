const CACHE = 'daily-news-v1';
const STATIC = [
  '/daily-news-site/',
  '/daily-news-site/style.css',
  '/daily-news-site/manifest.json',
  '/daily-news-site/icons/icon-192.png',
  '/daily-news-site/icons/icon-512.png',
];

// インストール時に静的アセットをキャッシュ
self.addEventListener('install', (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(STATIC)));
  self.skipWaiting();
});

// 古いキャッシュを削除
self.addEventListener('activate', (e) => {
  e.waitUntil(
    caches.keys().then((keys) =>
      Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k)))
    )
  );
  self.clients.claim();
});

// ネットワーク優先、失敗時はキャッシュを返す
self.addEventListener('fetch', (e) => {
  e.respondWith(
    fetch(e.request)
      .then((res) => {
        const clone = res.clone();
        caches.open(CACHE).then((c) => c.put(e.request, clone));
        return res;
      })
      .catch(() => caches.match(e.request))
  );
});
