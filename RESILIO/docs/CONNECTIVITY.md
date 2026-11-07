# Connectivity and offline operation

## A. Connected to a hosted server
Browser → HTTPS → Django → SQLite. The browser uses same-origin Fetch requests with session cookies and CSRF headers. Public snapshots are fetched every 30 seconds. Confirmation messages appear only after successful server responses; device-only saves are explicitly identified.

For actual hosting: configure a production WSGI server, HTTPS reverse proxy, `DJANGO_SECRET_KEY`, `RESILIO_DEBUG=0`, explicit allowed hosts, HTTPS trusted origins and secure cookies (`RESILIO_HTTPS=1`). Run `collectstatic` and serve `staticfiles/`. A static-only Netlify host cannot run this Django backend. This project does not change your Netlify website. Use `python manage.py check --deploy` with production settings before hosting. Internet hosting, HTTPS certificates and production load were not validated in this environment.

## B. No internet, local Wi-Fi available
A laptop runs Django and SQLite. Phones on the same router/hotspot reach the laptop. Coordination still works if the server is reachable: public resources, authentication, reservations, receipt confirmation, notifications and shelter operations require no external service after dependencies are installed.

1. Install Python dependencies beforehand. Find the laptop IPv4 address: `ipconfig` on Windows; `ip addr` on Linux; `ipconfig getifaddr en0` on many Macs. Example address below is illustrative, not discovered from your computer.
2. Set hosts to that exact address plus loopback. Do not use `*`.

Windows PowerShell:
```powershell
$env:DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost,192.168.1.20"
.\.venv\Scripts\python.exe manage.py runserver 0.0.0.0:8000
```
macOS/Linux:
```sh
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost,192.168.1.20 .venv/bin/python manage.py runserver 0.0.0.0:8000
```
3. Phones open `http://192.168.1.20:8000/` (substitute the laptop address). A phone's `127.0.0.1` points at the phone, not the laptop.
4. Permit inbound TCP 8000 on the laptop's private-network firewall profile only. Use the same trusted Wi-Fi. Router client isolation or some phone hotspots may prevent connections. Keep the laptop awake; an address change needs an updated URL and allowed-host value.
5. Same-origin HTTP lab usage normally needs no trusted-origin override. If hosting behind HTTPS on a different explicit origin, configure it as below. Never disable CSRF middleware or cookie protection.

HTTP on a phone's LAN address generally is **not** a secure context. IndexedDB may work with browser policy permitting, but offline application loading through a service worker will normally be unavailable. Feature detection displays this in Sync Center. Do not promise full offline reloads on HTTP LAN devices. Plain HTTP is suitable only for a trusted classroom exercise with fictional accounts/data.

### Trusted HTTPS for full offline features on phones
Use a local HTTPS reverse proxy (for example Caddy configured with a local CA, or an existing institutional HTTPS proxy) in front of Django. Obtain a certificate whose subject alternative name matches the exact hostname/IP. Install and explicitly trust the issuing CA on every participating phone/computer; simply ignoring a certificate warning does not reliably enable secure-context features.

Example topology: `https://resilio.lan` → proxy → `http://127.0.0.1:8000`. Ensure local DNS/hosts resolves the name on each client; mobile hosts files usually cannot be edited, so router DNS or a managed DNS record is preferable. Example environment (adapt to your actual certificate/name):
```sh
DJANGO_ALLOWED_HOSTS=resilio.lan,127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://resilio.lan
RESILIO_HTTPS=1
RESILIO_DEBUG=0
```
Set these as environment variables using your platform's syntax; the lines above describe configuration, not a complete proxy deployment. With DEBUG=0, serve collected static assets from the proxy. Forward the original Host header. This app does not blindly trust forwarded-proto headers. Browser Origin and Host must match the configured HTTPS name. Do not enter HTTP after enabling secure cookies.

## C. Server unreachable
- A previously installed service worker serves only a static, account-neutral application shell and assets. It never caches account pages, logout responses, session data or API responses.
- IndexedDB stores the latest **public-only** snapshot, minimal local requests, and the last authenticated account ID. The application shows the last successful public refresh time; cached stock can be stale. A new device with no cached item catalog must connect once.
- Only new help requests can be queued offline. Offers, reservations, receipt confirmations, edits, cancellations, moderation and shelter operations require a server response.
- A saved entry contains canonical item ID, quantity, unit via catalog, area, urgency, description, creating account ID and a stable UUID. Do not enter sensitive personal/medical details into public descriptions. Device data is not encrypted by this application; use a trusted device.
- **Pending sync** means locally stored and not yet confirmed. A failed retry becomes **Failed** with the server/network error. A successful retry becomes **Synced**, displaying the canonical server request ID.
- Synchronization first verifies the live authenticated account. Backend validation also enforces creating account ID. Each `(owner, client_id)` is unique. If a server save succeeded but its response was lost, retrying the stable ID returns the same request rather than creating a duplicate.
- Retries are explicit in Sync Center; the app does not silently send a request using a different account. Entries are filtered to the current/last account in the UI. This convenience is not a substitute for device access control. Sign-out clears the remembered account ID, and a signed-in different account cannot synchronize an earlier account's entries.
- Removing a local entry **does not cancel** a server request. Cancel the record from My Activity while online. Keep a failed or unconfirmed entry until its server status is resolved, so its identifier is preserved.
- Passwords and private API payloads are never saved to browser databases or Cache API. Private state exists in memory only. The session cookie is Django's normal HTTP-only cookie.
- Browser storage quota, private browsing restrictions or unavailable IndexedDB cause explicit errors. Theme switching still works for the current session if localStorage is blocked. Full offline app loading requires supported service workers in a secure context and a successful initial asset installation.

No Bluetooth, Wi-Fi Direct, true mesh discovery, disconnected-community relaying or emergency dispatch is implemented. Those require additional infrastructure or native networking support.

## Version 2 live coordination map
The Live map uses the same reachable server as resource posting. Authenticated users explicitly opt in to sharing a display label, role and their manually entered profile area. A map that remains open sends/reads heartbeats every 15 seconds; a participant is removed after 75 seconds without a recent heartbeat. This is an activity indicator, not a guarantee of instant reachability or geographic position. Sign-out or opt-out clears presence. Presence payloads are private and are never put in the offline snapshot/cache.

Canvas lines connect area/participant dots to the relief-center server. Decorative movement never represents actual travel or radio discovery. A separate Demo animation is labeled Simulation and creates no server records. If the server is unreachable, live participants are cleared and only previously cached public resource areas remain; offline request saving still works.
