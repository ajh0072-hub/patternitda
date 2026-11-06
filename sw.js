// 패턴잇다 서비스워커: 한 번 열면 인터넷 없이도 켜지게 한다.
// 앱을 고칠 때마다 VERSION 숫자를 올려야 설치된 앱이 새 버전을 받는다.
const VERSION = 'v13';
const CACHE = 'patternitda-' + VERSION;
const CORE = [
  './',
  './index.html',
  './manifest.webmanifest',
  './icons/icon-192.png',
  './icons/icon-512.png',
  './icons/apple-touch-icon.png'
];

// 새 버전은 받자마자 바로 적용한다 (앱이 파일 하나라 섞일 걱정이 없다).
self.addEventListener('install', e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).then(() => self.skipWaiting()));
});

self.addEventListener('activate', e => {
  e.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.filter(k => k.startsWith('patternitda-') && k !== CACHE).map(k => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', e => {
  const req = e.request;
  if (req.method !== 'GET') return;
  const url = new URL(req.url);

  // 앱 화면: 저장해 둔 걸 먼저 보여 줘서 오프라인에서도 열린다
  if (req.mode === 'navigate') {
    e.respondWith(caches.match('./index.html').then(r => r || fetch(req)));
    return;
  }

  // 글꼴(구글 폰트): 처음 받을 때 저장해 두고 다음부터는 저장본 사용
  if (url.hostname === 'fonts.googleapis.com' || url.hostname === 'fonts.gstatic.com') {
    e.respondWith(
      caches.open(CACHE).then(c => c.match(req).then(hit => hit || fetch(req).then(res => {
        c.put(req, res.clone());
        return res;
      }).catch(() => new Response('', { status: 504 }))))
    );
    return;
  }

  // 나머지 앱 파일: 저장본 먼저, 없으면 받아 온다
  if (url.origin === self.location.origin) {
    e.respondWith(caches.match(req).then(r => r || fetch(req)));
  }
});
