# RESILIO field coordination upgrade

This release implements the eight requested upgrades in sequence. It updates the
Django application; it does not change your deployed GitHub/Vercel project until
you upload and deploy its source.

## Install without losing existing users

LOCAL WINDOWS: stop the old server (Ctrl+C). Extract this ZIP to a different
folder. From the NEW RESILIO folder run upgrade-windows.bat and select your OLD
RESILIO folder. The updater backs up the old project and retains its database,
secret, environment settings and virtual environment. Start the old folder with
start-windows.bat. You do not need to create your administrator again.

MANUAL LOCAL UPDATE: back up your old folder and database. Copy the updated
source while preserving db.sqlite3, .local-secret, .env and .venv. With the
existing virtual-environment Python run `manage.py migrate`, then
`manage.py runserver`. Never replace a populated database with an empty file.

VERCEL: replace the source in your existing GitHub repository's RESILIO folder,
including migration 0005, coordination/data, new JavaScript modules and fonts.
Keep the current Vercel root directory, environment variables and Neon database.
Commit to trigger the normal build. The existing build hook runs migrations.
Do not upload your local .env, secrets, database or virtual environment.

Allow the new offline assets to install, then reload the page. This release uses
service-worker cache resilio-assets-v5. No new runtime package is required.

## Step 1 — Actual shelter and collection points

Shelters: an approved officer or administrator opens Shelters, adds a facility,
then selects Set shelter location. Choose a district/upazila, add the local area,
and choose a point on the map, use device location, or enter coordinates.
Confirm publication and save. Existing capacity and reservation counts remain.

Offers: the offer editor has the same optional pin controls. Public collection
and facility pins require explicit consent. A creator-provided pin is not an
independently verified measurement. The map retains clearly labeled approximate
district summary markers for records without a pin.

Requests: exact pins are private. Only the requester, authorized coordinators
and assigned delivery volunteers can retrieve them. Cancelling a volunteer's
assignment removes their request-pin access unless another valid assignment
still grants it. Public board/offline public snapshots omit request pins.

Use View exact pin to center the map. Enable Street background (online) for roads
and place labels. Street tiles are not bundled offline. Shelter distance sorting
uses actual facility pins and the device's last captured position. Distances are
straight-line measurements; no road routing or travel-time promise is provided.

## Step 2 — Upazila and local-area controls

Select Division -> District -> Upazila in forms and filters. Upazilas are validated
against their parent district. Offers, requests, shelters and profiles store the
selected code. Keep a ward, union, neighborhood or landmark in the local-area text.

The bundled reference snapshot has 494 entries from nuhil/bangladesh-geocode,
downloaded 2026-11-08 under MIT. It is not claimed as a complete, current government
registry. Select All / not listed and use local-area text when a place is absent.
Existing records are not guessed into an upazila. Division/district polygons are
bundled; upazila polygons and automatic GPS-to-upazila detection are not included.
Map upazila selection filters resources/facilities, not participant GPS positions.

## Step 3 — Bangla / English interface

Use the বাংলা / English button in the header. The choice persists on this browser,
including account forms and offline pages. Core navigation, form labels, actions,
status labels and critical coordination guidance have Bangla translations.
Noto Sans Bengali is bundled locally with its SIL Open Font License.

User-authored posts, contact details, names and message bodies stay in their
original language. Confirmation tokens such as SHARE, CANCEL, RESOLVED and
WITHDRAW remain literal English values; the Bangla instructions retain the token
to type. Some detailed technical validation messages remain in English.

## Step 4 — Emergency assistance

Sign in and open Emergency assistance. Enter the type, number of people, district,
area, description, optional contact and private pin. A server case number confirms
submission; an offline attempt is not a received emergency case. Keep the form open
to retry an uncertain submission with the same client identifier.

Approved officers/admins acknowledge a received case, assign an active volunteer,
then mark it resolved after checking the outcome. Owners/admins may cancel open
cases. Invalid status jumps are rejected. Requesters, authorized coordinators and
the assigned volunteer can see the private case. Notifications record key changes.
This is RESILIO coordination, not automatic government emergency-service dispatch.

## Step 5 — Availability freshness

Open resource cards show whether availability was confirmed within 24 hours.
Owners/admins use Still needed / available to reconfirm. Reconfirmation updates
only the confirmation timestamp; it does not change quantities or reservations.
Old migrated records begin unconfirmed. Editing an eligible open record also
reconfirms it. Staleness is recalculated in the browser for offline snapshots.
Stale posts remain visible with a clear label and are not automatically cancelled.

## Step 6 — Officer announcements

Approved officers/admins publish area-specific or nationwide announcements, with
an expiry within seven days. Expired, withdrawn or access-revoked announcements
are omitted from fresh public data. The author or an administrator can withdraw.
Issuer labels identify RESILIO roles; they do not imply government verification.
Offline snapshots show a warning and may miss later withdrawals until reconnection.
The client hides notices past their displayed expiry even in an offline snapshot.

## Step 7 — Assignment message threads

Open My Activity or Volunteer Desk and choose Assignment messages. The requester,
donor, assigned volunteer and authorized coordinators can read/send messages.
Messages are stored on the server and notify the other assignment participants.
Use Refresh messages for updates; older messages can be loaded in pages of 100.
Duplicate retries reuse a client identifier. There are no attachments, push
notifications or automatic offline message delivery in this release.

## Step 8 — Offline readiness

Sync Center reports whether essential boundary-map assets are cached, server
reachability, the public snapshot timestamp and this account's pending request
count. Check readiness again to refresh the report. Private cases, participant
responses, request pins and threads are never stored in the public service-worker
cache. A locally queued private request may contain a pin on that device; remove
its local copy in Sync Center when appropriate on a shared device.

## Verification and operating limits

Backend: `python manage.py test coordination` (42 tests). Optional DOM/theme and
Playwright browser suites are in tools/. The browser suite uses a temporary
SQLite database and simulated device positions; it does not certify physical GPS
accuracy. Database migrations retain existing users, password hashes, stock and
receipts. New pin/locality fields start empty. This is still browser-to-server
coordination. Bluetooth, Wi-Fi Direct, device mesh, road routing, automated
external weather feeds and emergency-service dispatch are not implemented.

## Fresh-install item catalog fix
Migration 0006 seeds the eight canonical items automatically during migrate.
Startup and upgrade scripts also run the repeatable initialize_catalog command.
This does not create demonstration accounts or stock, or overwrite existing items.
For an already extracted older copy, run the project's virtual-environment Python
with `manage.py initialize_catalog`, then refresh the page.

Windows locale fix: the Bangla locality directory is now read explicitly as
UTF-8. Older copies can change read_text() to read_text(encoding="utf-8") in
coordination/fieldops.py, then restart the server. This fixes /api/public/
returning HTTP 400 on Windows systems whose default encoding cannot read Bangla.
