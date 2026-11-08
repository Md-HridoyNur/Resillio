# RESILIO · Field coordination edition

**Latest release: all eight field-coordination upgrades are described in [FIELD_UPGRADE.md](FIELD_UPGRADE.md), with local and Vercel update steps.**

**Map upgrade for an existing deployment? Read [MAP_UPGRADE.md](MAP_UPGRADE.md). It includes district selection, private device location and separate pin sharing.**

**Want a public website? Open [START_HERE_VERCEL.md](START_HERE_VERCEL.md). The deployment configuration is already included. No hosting settings need to be edited in Python.**

**Already running the previous version? Start with [UPGRADE.md](UPGRADE.md). The included Windows updater preserves your existing administrator, passwords and database.**

Disaster Resource Coordination and Volunteer Management System

A complete local Django course project built from the supplied RESILIO HTML, CSS and JavaScript dashboard. It preserves the large condensed title, resource cards, grid background, red emergency controls, green supply indicators and supply/demand analysis. All operational data is now persisted in SQLite. No Netlify deployment or remote site changes are included.

## Quick start
Use Python 3.12 with pip and venv. Tested on Python 3.12 with Django 5.2.19. No Node.js, npm, React or separate database server is required. Fonts are included locally with licenses.

Unzip, open a terminal in the `RESILIO` folder, then:

Windows PowerShell:
```powershell
py -3.12 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe manage.py migrate
.\.venv\Scripts\python.exe manage.py seed_demo --password "Fictional-Demo!2026"
.\.venv\Scripts\python.exe manage.py runserver
```
macOS/Linux:
```sh
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python manage.py migrate
.venv/bin/python manage.py seed_demo --password 'Fictional-Demo!2026'
.venv/bin/python manage.py runserver
```
Open **http://127.0.0.1:8000/**. Alternatively run `start-windows.bat` or `sh start-unix.sh`; these create a virtual environment, install pinned dependencies, migrate and run. Seeding remains an explicit command. Initial installation needs internet access to download Python dependencies; subsequent local operation does not.

### Fictional demonstration accounts
If you used the seed command above, all four NEW accounts use `Fictional-Demo!2026`. The password is public demonstration information: use these accounts only with fictional data in a classroom or isolated local environment.

| Username | Role | Acceptance scenario |
|---|---|---|
| demo_requester | Community | Owns a 20 L drinking-water request in mirpur |
| demo_donor | Community | Owns a 50 L drinking-water offer in mirpur |
| demo_volunteer | Volunteer | Coordinates and submits delivery |
| demo_officer | NGO / Relief Officer applicant | Requires administrator approval in Administration |

Seed is repeatable: it creates missing catalog/demo rows, preserves existing records/passwords and never creates administrators. Labels identify demo records in the interface. Public registration creates community, volunteer or pending NGO / relief officer accounts; it cannot create staff. Officers must be approved by an administrator before coordination permissions become available. Create your administrator with `python manage.py createsuperuser` (use the venv Python shown above). That account works in the styled Administration screen and `/admin/`.

## Try the acceptance demonstration
1. Sign in as `demo_volunteer`. On Overview, find the 20 L water request. Open **View compatible offers**, reserve 20 L from the donor's 50 L offer.
2. Go to Volunteer Desk, click **Start delivery**, then **Submit delivered quantity**, entering 20.
3. Sign out and sign in as `demo_requester`. Open My Activity and **Confirm receipt**, typing RECEIVED. The request is fulfilled; the offer shows 30 L available. Only one delivery is counted. Repeated confirmation is rejected.
4. Partial case: for a fresh request reserve 20 but submit 12. After receipt, 12 L counts as delivered, 8 L is released, and the request retains 8 L unallocated need. Select another offer to complete it.
5. Offline case: sign in online once, open a new help request and use **Save request on device**. The Sync Center shows Pending sync. Simulate loss of server connectivity; the same button still works with the cached item catalog and remembered creating account. Reconnect, sign in as the creating account and retry synchronization. The entry becomes Synced with its server ID. **Verify same server ID** does not create a copy.
6. Toggle the theme, visit all screens, reload and verify the manual preference persists. **Use device theme** restores system tracking. Test both mobile and desktop sizes; see `docs/VALIDATION.md` for measured checks and limits.

## Access and communication in version 2

The header now prominently displays **Sign in** and **Join response**. The access page provides three main portals: **Administrator**, **NGO / Relief Officer**, and **Volunteer**. A separate Community / Donor entry remains available for affected people and supply donors. Portal selection checks the account's saved role; it never grants permissions. The Operations sidebar and numbered navigation labels have been removed. Navigation follows the current role.

An approved officer can coordinate supplies, assign a delivery to a registered volunteer, track assignments and maintain shelter capacity. They cannot approve other officers, review administrator reports, moderate another owner's post or confirm someone else's receipt as an administrator. Approve/revoke officers from the styled Administration workspace; changes are recorded and notified.

**Live map** includes bundled geographic boundaries for 8 divisions and 64 districts. Click a region or use the selectors. Resource/shelter summaries use representative district points; records without a district remain list-only. **Use my location** requests browser permission and displays a private blue device pin, accuracy circle and capture time. Select **View resources in [district]** to filter the detected district. Optional online street tiles provide roads/place labels.

Presence sharing and precise pin sharing are separate choices for signed-in participants. No coordinates are sent until the user confirms **Share my pin**. Only the latest coordinate is stored, and readings older than five minutes are hidden from participants. Stop sharing the pin, stop presence sharing or sign out to clear stored coordinates. Presence heartbeats run every 15 seconds while the map is open; absent participants disappear after 75 seconds. Private responses are never put in the offline cache. HTTPS or localhost is required for device location. See [MAP_UPGRADE.md](MAP_UPGRADE.md) for permissions, privacy, offline limits and installation.


## Screens and behavior
- **Overview**: live database counts, combined search/category/area/urgency/availability filters, resource board, area tiles and unit-safe supply/demand bars.
- **Request/offer forms**: canonical items/units, positive quantities, normalized area, description, urgency or offer expiry. Edits/cancellation are permitted only by the owner or administrator under workflow rules.
- **My Activity**: owned inventory, requests and involved delivery history; receipt confirmation by requester/admin.
- **Volunteer Desk / Officer Desk**: personal volunteer assignments; approved officer center-wide coordination, assignment to volunteers and validated transitions.
- **Shelters**: capacity list; staff and approved officers can add facilities, check in/out, reserve/release and convert reservations to occupancy.
- **Notifications**: private saved-event updates with unread/read state. Every 30 seconds, Fetch polling refreshes data unless a dialog is open, the tab is hidden or the Profile form is active. This is not WebSocket communication.
- **Sync Center**: device requests, Pending sync/Failed/Synced states, retry, stable server IDs and local deletion.
- **Administration**: officer approvals/revocations, reports and reasoned decisions, moderation through board controls, operations and audit history. Built-in Django admin provides account management and read-only operational records; operational mutations use the validated application workflow.
- **Crisis Mode**: native accessible modal; category buttons close it and open an urgent prefilled request form. All validation/save errors are displayed inside the active dialog.

## Connectivity
See `docs/CONNECTIVITY.md` for LAN and HTTPS configuration. This is browser-to-Django coordination, with offline help-request queuing; it does not implement Bluetooth, Wi-Fi Direct, peer-to-peer mesh, automatic inter-community relays, or emergency-service dispatch. Cached availability is stale until refreshed. Offers, reservations, deliveries and shelter changes require the server.

## Data and security
`docs/ARCHITECTURE.md` describes tables, allocation math, transaction boundaries, permissions, API and course concepts. SQLite uses `BEGIN IMMEDIATE` for operational transactions, not `select_for_update()`. Conflicting writes return HTTP 409. Quantities and receipt transitions are revalidated on the server. Cookies, password hashing and CSRF use Django's normal frameworks.

A per-install `.local-secret` and `db.sqlite3` are generated locally and excluded from this ZIP. Keep the secret stable between restarts or sessions will expire. For hosting, set `DJANGO_SECRET_KEY`, explicit `DJANGO_ALLOWED_HOSTS`, `RESILIO_DEBUG=0`, `RESILIO_HTTPS=1`, serve static files and use a production WSGI server/reverse proxy. `runserver` is for lab use. Django's deployment checklist: https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/ .

## Tests
```sh
python manage.py check
python manage.py makemigrations --check --dry-run
python manage.py test coordination --verbosity 2
```
Use your venv Python. For an on-disk SQLite concurrency test:
```sh
RESILIO_TEST_DB=/tmp/resilio-test.sqlite3 python manage.py test coordination.tests.Concurrency --noinput
```
PowerShell: set `$env:RESILIO_TEST_DB` to a disposable absolute file path, then run the test. This test database is created and deleted by Django; never point it at real data.

`docs/VALIDATION.md` distinguishes executed checks from manual browser checks. Optional browser tests are in `tools/` and are not runtime dependencies.

## Project contents
- `original-base/`: byte-for-byte copies of your three uploaded `(3)` files. The instruction text mentions `(2)`; the supplied `(3)` versions are the actual source preserved here.
- `config/`: settings, URL routing, WSGI.
- `coordination/`: models, migrations, validation/workflow services, views, forms, tests, demo command and admin setup.
- `templates/`, `static/resilio/`: Django shell/account templates, vanilla JavaScript, themes, service worker and fonts.
- `docs/`: requirements, architecture, connectivity, validation and acceptance checklist.

Original behavior: fixed resource arrays, random alerts, synthetic network nodes/latency, static percentages and toast-only actions. These remain unchanged only in `original-base/` for reference; the running application replaces them with database operations and an honest area-based visualization.

Dependencies are pinned in `requirements.txt`. Django 5.2 is an LTS line supported through April 2028; version 5.2.19 is the November 2026 security patch. Official sources: https://www.djangoproject.com/download/ and https://docs.djangoproject.com/en/5.2/releases/5.2.19/ .

Hosted PostgreSQL uses an operational singleton row lock; local SQLite uses BEGIN IMMEDIATE. See `docs/VERCEL_TECHNICAL.md` for configuration, test status and preview database isolation.

## Field coordination release
Exact public facility/pickup pins, private request pins, upazila reference selectors, Bangla interface support with a bundled font, private emergency cases, 24-hour availability confirmation, officer announcements, assignment message threads and offline readiness are implemented. Migration 0005 adds the relevant fields/tables without replacing existing accounts or records. Read FIELD_UPGRADE.md for privacy, reference-data limitations and the eight demonstration flows.
