# Validation report

Executed 7 November 2026 in a Linux workspace using Python 3.12, Django 5.2.19, SQLite, headless Chromium 153.0.8010.0 and Playwright 1.64.1. This report distinguishes automated assertions, screenshot review and checks requiring physical devices or deployment.

## Executed results
| Check | Result | Evidence / scope |
|---|---|---|
| Django system check | PASS | No issues |
| Migration consistency | PASS | `makemigrations --check --dry-run`: no changes detected |
| Backend suite | PASS, 29 tests | `coordination/tests.py`, including officer access and presence restrictions |
| On-disk SQLite concurrency | PASS, additional run | Two simultaneous HTTP reservation requests against an actual temporary SQLite file; one succeeds, the other rejects/conflicts; reserved total 15 L against 20 L need |
| Theme behavior | PASS, 9 checks | `tools/test_theme.cjs`; first-visit preferences, manual persistence/reload, system changes, reset, invalid storage values, blocked localStorage, accessible toggle state |
| Frontend DOM behavior | PASS, 12 checks | `tools/test_dom.cjs`; safe text rendering, searches, dialog payloads, crisis prefill, canonical units, screens, IndexedDB pending entries, sync identity reuse and wrong-account prevention |
| Browser theme behavior | PASS | Real Chromium: dark system start; manual light selection survives reload and system changes; reset resumes live system preference |
| Browser full delivery workflow | PASS | Actual session login, CSRF-protected Fetch, reserve 20 L, start, submit 20 L, requester receipt; request fulfilled, offer 30 L, one receipt |
| Browser offline reload | PASS | Service worker installed at localhost; browser set offline; request saved in IndexedDB; full page reload shows cached shell, public snapshot date and pending queue |
| Browser sync and retry | PASS | Reconnect and synchronize; server ID displayed; second synchronization creates no additional request |
| Browser desktop/mobile layout | PASS | 1440 px and 390 px widths; light and dark; overview, activity, volunteer, shelters, notifications, sync, administration, profile; no page-level horizontal overflow |
| Dialog keyboard behavior | PASS | Native Escape closes crisis/request dialogs; Tab cycles within the open editor; no browser JavaScript page errors |
| Screenshot review | PASS | Desktop/mobile, both themes; overview/cards/quantity bars, forms, crisis and styled administrator workspace inspected. Internal QA images are not shipped as user data. |
| Persistence | PASS | Inventory written in one Python/Django process, read and asserted in a separate process using the same temporary on-disk SQLite database |
| Three access portals and officer approval | PASS | Real browser registration of a pending officer, administrator approval, saved-role portal checks in backend tests |
| Live presence across two browser sessions | PASS | Admin and volunteer opt in with different labels; both appear through the same Django server; volunteer opt-out removes the participant |
| Animated simulation and cache privacy | PASS | Real canvas image changes while simulation runs; explicit SIMULATION banner; Cache API contains no private API responses |
| In-place upgrade from version 1 | PASS | Original ZIP migrated in a temporary existing installation; updater creates backup; existing administrator/password, 50 L inventory and .local-secret preserved |
| Original source preservation | PASS | All three `original-base/` copies byte-compared with the uploads |
| Artifact hygiene | PASS | ZIP excludes runtime database/secret, caches, dependencies and virtual environments |

### Backend suite coverage
- Officer registration requiring an organization; unapproved access restrictions; administrator approval/revocation; no self-assignment of staff privileges; volunteer assignment restrictions; correct-role login validation.
- Opt-in presence, 75-second expiry, authenticated-only visibility, own-account consent, heartbeat not overriding opt-out and logout clearing presence.
- Registration, authentication and inability to self-register as administrator.
- CSRF enforcement, owner permissions and volunteer/staff restrictions.
- Resource creation/edit/cancellation, normalization and invalid quantity rejection.
- Different items/units cannot match; expired supply is excluded.
- Full fulfilment, partial fulfilment, one-to-many and many-to-one allocations.
- Released reservations, immutable allocated records and retained history.
- Invalid transitions, over-reservation, excessive delivered quantity, requester/admin receipt authorization, duplicate confirmation.
- User-specific notifications/read state, report review and audit creation.
- Shelter occupancy/reservation/conversion/release/check-out bounds and database constraints.
- Stable offline IDs, same-account retry deduplication and account mismatch rejection.
- Repeatable seed command preserving quantities and existing passwords.
- Concurrent reservations using independent connections/HTTP clients.

### What the real browser suite does not assert
The browser acceptance run completes the full delivery and offline-to-online workflows against real Django and SQLite. Partial deliveries, invalid actor transitions, report review and shelter boundary cases are exercised in backend integration tests; the browser suite does not click through every permutation. DOM checks use mocked API responses for isolated frontend behavior. The theme VM check simulates storage failure; a real browser with enterprise storage policy was not available.

## Not executed here
- Actual Windows or macOS launchers on those operating systems. Commands are supplied and use ordinary Python/venv operations; only Linux execution was tested.
- Physical Android/iOS devices on a laptop hotspot/router, local firewall rules, router client isolation, LAN certificate/CA installation.
- Safari/Firefox browser compatibility or screen-reader testing.
- Hosted HTTPS deployment, production security configuration, scale/load testing or disaster-response field reliability.

Localhost service-worker behavior was tested; HTTP LAN access from a phone must not be assumed to receive those privileges. Follow `CONNECTIVITY.md` for trusted HTTPS and device-level testing.

## Reproduce
Application tests require only `requirements.txt`:
```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test coordination --verbosity 2
```
Use a disposable on-disk test DB for the separate concurrency run, as described in README.

Optional developer theme and DOM checks (Node is not required by the application):
```sh
npm install --prefix tools
node tools/test_theme.cjs
node tools/test_dom.cjs
```
The DOM checks use jsdom 31.0.0 and fake-indexeddb 6.2.7, pinned in `tools/package.json`. Keep `tools/node_modules/` out of any redistributed ZIP.

Optional real-browser suite:
```sh
python -m pip install -r requirements-browser.txt
python -m playwright install chromium
python tools/browser_acceptance.py
```
This suite creates and deletes a temporary SQLite database, with fictional users and a fictional administrator. `CHROMIUM_PATH` can select a preinstalled compatible Chromium executable. The run in this environment used that option after the normal browser download was unavailable. There is no requirement to install Node/npm to run these Python browser checks or the application. Browser binaries and automation dependencies are not included in the deliverable.

## Version 2 visual changes reviewed
Header account actions, three-portal access page, login and officer registration forms, role-aware horizontal navigation, upgraded hero and live coordination map were checked at 1440 px and 390 px widths in both themes. The obsolete Operations sidebar was removed. Existing resource, receipt, offline-sync and duplicate-prevention browser acceptance checks continue to pass. Physical LAN phones and actual routers remain outside the executed scope.

## Vercel-ready edition validation
The SQLite integration suite now has 29 passing tests, including cloud catalog initialization and private administrator bootstrap validation, repeatability, no password reset and refusal to elevate an existing public user. `tools/test_cloud_settings.py` passed subprocess checks for local SQLite fallback, PostgreSQL URL parsing, required HTTPS/SSL and secrets, exact automatic hosts/origins, isolated preview DB configuration and unsafe setting rejection. A fresh temporary database ran the Vercel build hook twice, applied migrations 0001–0003, initialized eight catalog items and retained the original bootstrap password. Static collection succeeded. The local real-browser delivery, offline sync, officer approval, two-browser presence and responsive theme suite still passes.

Actual Vercel deployment, hosted Neon connectivity and native PostgreSQL contention are pending connection to the user's own accounts. A native PostgreSQL server could not start under the available process permissions; these are not reported as executed tests. See `VERCEL_TECHNICAL.md`.
