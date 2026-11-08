# Architecture and course mapping

## Layers
Django serves an account-neutral HTML shell, account forms and JSON endpoints. Vanilla JavaScript constructs safe DOM nodes using `textContent` and `createElement`, handles event listeners, filters the public board and uses Fetch for server operations. Django services validate permission and workflow rules; the ORM persists normalized records in SQLite. CSS theme variables style every application screen and native dialog. Bundled Nimbus Sans Narrow and DejaVu Sans fonts avoid CDN requests. Reduced-motion settings disable transitions.

The unchanged original files are retained for provenance. Their synthetic mesh, battery, distance, latency, counters and random events are not used by the running application. Area tiles visualize actual normalized database areas; numerical lists and text labels provide alternatives to chart bars.

## Relational schema
| Table | Key relationships and invariants |
|---|---|
| Django User | Hashed passwords, sessions, staff/superuser permissions |
| Profile | One-to-one User; community/volunteer/coordinator roles; organization, officer approval, normalized area, opt-in presence label and indexed last_seen |
| Category | Unique canonical name |
| Item | Category FK; unique canonical item name; immutable unit in normal operations |
| Offer | Owner and Item FKs; quantity > 0; status/timestamps; optional expiry |
| HelpRequest | Owner and Item FKs; quantity > 0; urgency; unique nullable `(owner, client_id)` |
| Assignment | Offer/Request/Volunteer FKs; quantity > 0; 0 ≤ submitted delivery ≤ reserved quantity; status |
| Delivery | One-to-one Assignment; positive confirmed quantity; confirmer/date; permanent receipt |
| Notification | User FK; text, read flag, timestamp |
| Report | Reporter FK; exactly one Offer or HelpRequest FK; reason, reviewer, decision/date |
| Shelter | Unique facility name; normalized area; nonnegative capacities; occupied + reserved ≤ total |
| Audit | Actor FK; action, target, detail, timestamp |

Foreign-key operational history uses PROTECT. Record area/status, assignment status and relevant unique/FK fields have database indexes. Offer and request remain separate models; shelter spaces are never confused with supplies. Category/item compatibility uses the same canonical Item FK, so litres of drinking water never match purification tablets. Units cannot be changed through the application. Django admin operational tables are read-only to preserve service invariants.

## Allocation and delivery math
Let A be assignments with status Assigned/In progress/Awaiting confirmation and D be confirmed Delivered assignments:

`available supply = offer.quantity − sum(A.quantity) − sum(D.delivered_quantity)`

Expired/cancelled offers expose zero available stock. Existing reservations survive expiry so physical deliveries already underway can be confirmed; no new allocation can use expired stock.

`remaining need = request.quantity − sum(D.delivered_quantity)`

`unallocated need = request.quantity − sum(A.quantity) − sum(D.delivered_quantity)`

Partial submissions keep the full reservation until receipt confirmation. On confirmation, the assignment becomes Delivered and only its confirmed actual quantity is subtracted, releasing its unused portion. Cancellation during Assigned/In progress releases all of its reservation. Awaiting confirmation cannot be cancelled, preventing supply from being reused before a receipt dispute is resolved. Administrators may confirm pending receipts; this version has no separate dispute/rejection workflow.

Requests become Fulfilled only after confirmed receipts cover the quantity. An offer may supply several requests; a request may receive several offers. Editing an allocated record is blocked if it has any non-cancelled assignment, including completed history. Cancellation is blocked while active reservations exist. Fulfilled requests and completed deliveries remain in history.

Matching requires the same Item, positive available supply and open request with unallocated need. It ranks same-area offers first, then earlier expiry, then available quantity. Reasons explicitly state area/partial coverage/expiry. Distance is not invented. Cross-area suggestions require human transport coordination.

## SQLite concurrency
Settings use Django's SQLite `transaction_mode='IMMEDIATE'`. Each operational POST enters `transaction.atomic()` before reading mutable quantities. `BEGIN IMMEDIATE` obtains the SQLite writer reservation before stock/need checks. A second connection waits up to the configured 8 seconds or receives a conflict. Once the first transaction commits, the next writer rechecks current values. It cannot reserve based on an earlier unprotected stock read. This serializes writers at database level; it is suitable for a modest local course project, not a high-volume national response platform.

No reliance is placed on `select_for_update()` (SQLite does not provide its row-lock semantics). Database constraints are a second layer for scalar quantities, unique receipts/client IDs and shelter capacity. `OperationalError`/integrity conflicts return 409 and leave the local sync entry intact. Backend tests include two simultaneous HTTP requests and a separate on-disk SQLite concurrency run.

## Permissions
| Actor | Authorized operations |
|---|---|
| Public | Public resources, counts, shelter capacity, catalog |
| Community | Create offers/requests; permitted edits/cancellation of owned records; own profile/notifications; report posts; confirm own request receipts |
| Volunteer | All community actions plus reserve supply; start/submit/cancel own assignments |
| Approved NGO / Relief Officer | Community actions; center-wide assignment view; reserve/assign supply to volunteers; start/submit/cancel assignments; maintain shelter capacity. Approval can be revoked. |
| Staff administrator | Moderation of open resources under the same allocation rules; assignments/receipt confirmation; shelter operations; report review; audit workspace |

Public registration allows community/volunteer/pending coordinator only. Coordinator privileges require Profile.approved set through the administrator approval endpoint. Posting `is_staff` or `is_superuser` cannot elevate permission. `createsuperuser` is the supported administrator setup. Staff status is evaluated on the backend. An account cannot read another account's notification list, mark their notifications read or sync their queue entry. All operational POSTs require session auth and CSRF. GET /api/me/ is private and sends no-store headers.

## Routes
| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Application shell; sets CSRF cookie |
| `/accounts/login/`, `/accounts/logout/` | Django auth | Login form; POST logout |
| `/access/` | GET | Three staff portals plus community/donor entry |
| `/api/presence/` | GET/POST | Authenticated opted-in presence list / own heartbeat and consent; 75-second expiry |
| `/api/approve/` | POST | Administrator-only officer approval/revocation with audit and notification |
| `/register/` | GET/POST | Validated account registration |
| `/api/public/` | GET | Public catalog, resources, shelters, per-unit analytics, counts and snapshot date |
| `/api/me/` | GET | Current account, own notifications/record IDs, involved assignments; staff reports/audit |
| `/api/matches/?request=ID` | GET | Authenticated compatible offer suggestions |
| `/api/resource/` | POST | Create/edit validated record; idempotent offline request save |
| `/api/cancel/` | POST | Cancel open owned/admin record if no active allocation |
| `/api/reserve/` | POST | Volunteer reservation |
| `/api/transition/` | POST | start, submit, cancel, confirm |
| `/api/shelter/` | POST | Staff facility create/capacity operations |
| `/api/report/`, `/api/review/` | POST | Report post / staff review |
| `/api/read/`, `/api/profile/` | POST | Own notification state / own profile |
| `/sw.js` | GET | Root-scoped service worker, explicit static allowlist |
| `/admin/` | Django admin | Accounts and operational record inspection |

JSON errors use 400 for invalid input, 401 for missing authentication, 403 for unauthorized/CSRF, 404 for missing records and 409 for database conflicts. Form errors remain in the active dialog. Native `<dialog>` supplies modal focus management, Escape behavior and removes closed dialogs from keyboard navigation. The crisis modal closes before opening the request form.

## Theme and offline design
The small theme script executes before CSS. On first visit it reads the system preference; valid manual values in localStorage override it. Without a manual choice, system changes apply immediately. Theme toggles expose labels and aria-pressed state. Use device theme clears a manual choice. Storage exceptions are caught, retaining session switching. CSS-based bars inherit variables so changing theme does not leave old canvas colors.

The service worker caches only seven explicit account-neutral static URLs. Navigation fallback applies only to `/`. Account/admin pages and APIs are never cached by the worker. IndexedDB holds one public snapshot and account-associated local request records. UUID generation feature-detects `getRandomValues` and does not require `randomUUID`. Request IDs are non-security idempotency keys; authorization always comes from the Django session.

## Course concepts
| Course topic | Implementation |
|---|---|
| HTML5 semantic structure | Header/nav/aside/main/footer, accessible forms and dialogs |
| CSS3 and responsive design | Theme variables, grid/flex layouts, local fonts, media queries |
| JavaScript DOM/events | Safe element construction, filters, modal workflows, keyboard-native controls |
| Fetch/HTTP | Same-origin JSON GET/POST, status codes, session/CSRF headers, periodic polling |
| Django MTV | Models, URL routing/views, templates, Django auth forms |
| Database and ORM | FKs, checks, uniqueness, indexes, migrations, aggregate counts |
| Transactions | BEGIN IMMEDIATE, atomic workflows, concurrent reservation checks |
| Authentication and authorization | Password hashing, sessions, roles, owner and receipt checks |
| Progressive web features | Service worker/Cache API, IndexedDB, secure-context detection |
| Validation and testing | Backend integration/concurrency, theme tests and optional browser acceptance suite |

## Version 2 presence and role behavior
`network.js` uses locally bundled Leaflet and geoBoundaries polygons. Division/District models and migration 0004 provide a canonical geographic catalog. Requests, offers, shelters and profiles have optional district references; existing free-text areas remain intact. Representative district markers are labeled approximate and never presented as exact pickup locations.

Device coordinates stay in memory unless explicitly shared through authenticated POST `/api/location/`. The service requires presence opt-in, boolean consent, finite coordinate/accuracy bounds and a fresh timestamp. It stores only the latest point on the caller's profile; no target user is accepted. GET `/api/presence/` exposes fresh shared coordinates only to signed-in users. Old points are hidden after five minutes. Opt-out/presence-off/logout clears coordinates. Public data and offline caches omit precise participant data. Heartbeats still use the server; no Bluetooth or peer-to-peer transport is implemented.

The service worker explicitly caches only bundled static assets and public offline shell, including the small GeoJSON files. External street tiles and authenticated API responses are excluded. Source attribution and limitations are documented in MAP_UPGRADE.md and static/resilio/geo/ATTRIBUTION.txt.

## Field coordination
Migration 0005 adds paired bounded coordinate fields and locality codes to offers, requests and shelters. Requests are excluded from the public pin serializer; authorized request-pin data is carried in /api/me/ only. The current district/upazila pairing is validated against a bundled MIT reference snapshot. /api/shelter_place/ changes only facility geography and retains capacity values.

EmergencyCase stores a private, duplicate-safe case and a controlled status machine; /api/emergency/ checks coordinator/owner permissions before transitions. Announcement has controlled authorship, district audience, withdrawal and expiry. AssignmentMessage is scoped to existing assignment participants and coordinators; unique client identifiers prevent duplicate retries. GET /api/messages/?assignment=ID returns the latest 100 in chronological display order and supports before=ID for older pages. All mutations use the existing transactional operational mutex.

/api/reconfirm/ updates only confirmed_at. A 24-hour freshness label is computed server-side and recalculated client-side for offline snapshots; this is not independent verification. The service worker remains an explicit same-origin static asset allowlist. Core labels/actions are translated by a local dictionary; free-form user content is excluded and protocol values remain stable. See FIELD_UPGRADE.md for operating boundaries.
