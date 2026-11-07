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
`network.js` animates an explicitly schematic area diagram around one relief-center server. Real presence comes from authenticated opt-in Profile records; no invented real-user coordinates or device proximity are used. Presence is fetched and heartbeats sent every 15 seconds while the map is mounted. The backend excludes records older than 75 seconds and clears last_seen on logout. Inactive/unshared accounts never appear. A list alternative provides labels, roles, chosen areas and last-heartbeat text. The demo switch draws ten fictional participants under a simulation banner; it writes nothing. Reduced-motion preference fixes the decorative positions. Canvas colors read the shared theme variables on redraw.

Approved coordinators can see center-wide assignments and choose an active volunteer on reservation. Reserve still executes the same IMMEDIATE stock/need checks. Coordinators may manage status updates and shelter capacities but have no staff flag, no admin-site access and no administrator receipt/report/approval authority.

Migration 0002 adds fields without altering existing account passwords, record quantities or delivery history. The updater backs up the old project and SQLite database before copying source, skips virtual environments and runtime secrets/databases, then migrates in place.

## Hosted database adapter
The Vercel-ready edition reads PostgreSQL from DATABASE_URL while preserving local SQLite. CoordinationLock is a singleton row inserted by migration 0003. Operational POSTs acquire this PostgreSQL row lock inside their atomic transaction before reading mutable state; SQLite retains BEGIN IMMEDIATE. Catalog and optional administrator bootstrap jobs use the same lock. This intentionally serializes writes to preserve cross-offer/request invariants in a small course deployment. Hosted configuration/build behavior and unexecuted deployment tests are documented in VERCEL_TECHNICAL.md.
