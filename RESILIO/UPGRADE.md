# Upgrade your existing project — keep your administrator and saved data

You already created an administrator account. Do **not** create it again.

## Windows (recommended)
1. Stop the currently running server with **Ctrl+C**.
2. Extract the new ZIP into a **different folder**. Do not delete the old project.
3. Inside the newly extracted `RESILIO` folder, double-click **upgrade-windows.bat**.
4. Paste the path of your **old** RESILIO folder containing `manage.py`. You can copy it from the Windows Explorer address bar. Example: `C:\Users\YourName\Downloads\RESILIO_Django_Project\RESILIO`.
5. The updater creates a timestamped backup beside the old project, updates source files installs the updated requirements and runs migrations using your existing virtual environment. It preserves `db.sqlite3`, `.local-secret`, `.env` and `.venv`.
6. Open your **old project folder** in VS Code and run the familiar command:
```powershell
.\.venv\Scripts\python.exe manage.py runserver
```
7. Open http://127.0.0.1:8000/ . Let the new service worker install, then reload the page (Ctrl+F5 if needed). Sign in through **Administrator** with the username and password you already created.

If `py` is unavailable, run the updater using a working Python command:
```powershell
python tools\upgrade_existing.py --target "C:\path\to\old\RESILIO"
```
Run that from the newly extracted project. The updater does not need Django installed in that Python interpreter; migration uses the old project's virtual environment.

## Manual alternative / macOS / Linux
Back up the old project first, including the database and `.local-secret`. Copy the new source files over the old project while preserving `.venv`, `db.sqlite3`, `.local-secret` and `.env`. Then run:
```sh
.venv/bin/python manage.py migrate
.venv/bin/python manage.py runserver
```
Windows uses `.\.venv\Scripts\python.exe` in place of `.venv/bin/python`.

Migration `0003` additionally creates the operational lock used by PostgreSQL; it preserves existing data. Installing the added database dependencies needs internet once.

The `0002` migration adds officer approval and opt-in participant presence; it does not replace existing users, passwords, stock, receipts or local request identifiers. Officer applications require administrator approval. Community and volunteer accounts continue working in their existing roles. No fresh demo seeding is required to upgrade.

## What changed
- Three prominent staff access portals: Administrator, NGO / Relief Officer, Volunteer.
- Community / Donor access remains available for affected people and donors in the proposal.
- Sign-in and Join response buttons moved into the header with stronger contrast.
- Removed the Operations sidebar/numbered labels; navigation now follows the account role.
- Officer approval/revocation, officer desk, assignment to volunteers and shelter controls.
- Live coordination map on Overview and a full Live map screen, with accessible area/participant lists.
- Presence sharing is opt-in. Signed-in participants can see shared labels, roles, chosen areas and recent heartbeats through the same server. It is not GPS tracking.
- Demo animation recreates the moving-node presentation with an explicit simulation label.
- Hosted internet and same-Wi-Fi laptop-server operation use the same Django endpoints. Server-unreachable request storage and duplicate-safe synchronization remain in place.
