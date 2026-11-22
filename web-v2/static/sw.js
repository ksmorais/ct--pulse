/* PWA installability only: private responses are never cached. Online use required. */
self.addEventListener('install',()=>self.skipWaiting());
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('fetch',event=>{if(event.request.method==='GET'&&new URL(event.request.url).origin===self.location.origin&&!new URL(event.request.url).pathname.startsWith('/api/'))event.respondWith(fetch(event.request));});
