# Bangladesh map upgrade

RESILIO now includes a geographic map with 8 divisions and 64 districts. Select
an area on the map or through the division/district controls. Requests, offers,
shelters and user profiles can be assigned to a district. Existing free-text
areas are retained. Old records without a district stay in the list until edited;
the application does not invent their positions.

## Update your existing Vercel website

1. Extract this ZIP. Upload the updated contents of RESILIO into your existing
   GitHub repository's RESILIO folder, keeping the same directory structure.
   Include the new migration, geography.js, geo folder and vendor/leaflet folder.
2. Keep your existing Vercel environment variables and Neon database unchanged.
   Do not upload .env, .local-secret, .venv or a local db.sqlite3.
3. Commit the files. Vercel will rebuild using the existing configuration. Its
   build script runs migrations, including 0004 which seeds divisions/districts.
4. Open your deployment and reload once. Open Live map and choose a district.
   Existing users and records remain in the connected database.

Local update: with the project's Python environment, run
`python manage.py migrate` then `python manage.py runserver`.
You do not need to create your administrator account again.

## Find your location

Open Live map and select Use my location. Accept your browser's permission prompt.
The blue marker shows the device's browser-reported position, with an accuracy
circle, coordinates, capture time and detected district where possible. Accuracy
varies by device; desktop readings can be approximate. GPS is not proof of identity
or a verified rescue location. A location reading does not guarantee a street
address. Use View resources in [district] to filter help around your detected
district. Enable Street background (online) for roads and place labels.

Location access requires HTTPS (as on Vercel) or localhost. A phone viewing a
laptop through an ordinary HTTP LAN address normally cannot use browser
geolocation; use the division/district selectors or trusted HTTPS.

Location is private in page memory by default. Signed-in users may separately
choose Share my pin and confirm SHARE. This shares their latest reported position
and accuracy with signed-in participants. Only the latest coordinate is stored;
there is no coordinate history. New coordinates are sent only while the map is
open and tracking is active. Pins older than five minutes are hidden from the
presence API, though the latest stored coordinate remains until sharing is stopped.
Stop sharing my pin, stop presence sharing, or sign out to clear the server copy.
Stop location stops device tracking; use Stop sharing my pin to remove a shared
server copy as well. Browser/device location reports can be inaccurate or spoofed.

## Offline and communication limits

After one successful load and offline installation, the boundary map, selectors
and last public snapshot are available offline. Requests can be queued using the
existing offline workflow. Private participant responses are never cached by the
service worker. Online street tiles need internet and are not downloaded offline.
The map itself creates no network between devices. Live coordination still needs
a reachable RESILIO server (internet or local Wi-Fi/hotspot). Bluetooth, Wi-Fi
Direct and phone-to-phone mesh relaying are deferred; they are not implemented.

## Data and checks

Bundled geoBoundaries division data represents 2015; district data represents
2020. Names/codes are normalized. Boundaries are simplified and not survey-grade.
Full source and license attribution is in static/resilio/geo/ATTRIBUTION.txt.
Leaflet 1.9.4 is bundled locally; no Node installation is needed to run the site.
Run `python manage.py test coordination` for backend checks. Optional browser
and DOM suites are in tools/ and use separate test dependencies.
