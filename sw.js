/* 常用漢字 학습장 service worker: 앱 파일을 캐시해 오프라인에서도 열리게 한다.
   VERSION 값이 바뀌면 캐시가 새로 만들어지고 이전 캐시는 지워진다. */
const VERSION = 'bbceb96c85';
const CACHE = 'joyo-kanji-' + VERSION;
const BASE = new URL('./', self.location).href;
const FILES = ['kanji.html', 'kanji-strokes.js', 'manifest.webmanifest', 'icons/icon-192.png', 'icons/icon-512.png', 'icons/icon-180.png'];
const URLS = FILES.map(f => new URL(f, BASE).href);

self.addEventListener('install', ev => {
  ev.waitUntil(caches.open(CACHE).then(c => c.addAll(URLS)).then(() => self.skipWaiting()));
});
self.addEventListener('activate', ev => {
  ev.waitUntil(caches.keys().then(keys => Promise.all(keys.filter(k => k.startsWith('joyo-kanji-') && k !== CACHE).map(k => caches.delete(k)))).then(() => self.clients.claim()));
});
self.addEventListener('fetch', ev => {
  const url = new URL(ev.request.url); url.hash = ''; url.search = '';
  const key = url.href;
  if (!URLS.includes(key)) return;   // 다른 파일(index.html 등)은 건드리지 않는다
  ev.respondWith(
    fetch(ev.request).then(res => {
      if (res && res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(key, copy)); }
      return res;
    }).catch(() => caches.match(key))
  );
});
