# Put RESILIO online — no Python settings editing

Use this fresh package for GitHub/Vercel. Keep your working local project as a backup.

## 1. Upload the clean project to GitHub
Open https://github.com/new and create a repository named `resilio` (private is fine). On the repository page choose **upload an existing file**, or **Add file → Upload files**.

Upload the **contents inside this package's RESILIO folder**, not the ZIP itself. You should see `manage.py`, `requirements.txt`, `pyproject.toml`, `vercel.json`, `config/`, `coordination/`, `static/` and `templates/` at the repository root. Commit the upload to `main`.

Use the freshly extracted package: do not upload your existing `.venv`, `db.sqlite3`, `.local-secret`, `.env` or real account data.

## 2. Create the online database
Open https://console.neon.tech and create a PostgreSQL project. In **Connect / Connection details**, copy its PostgreSQL connection string with `sslmode=require`. Keep the complete value private. This will be `DATABASE_URL`.

If a pooled/direct switch is available, use the pooled URL for `DATABASE_URL` and optionally copy the direct URL into `DATABASE_URL_UNPOOLED` for migrations. An integration that already provides these variables works too. The code reads the database URL and selects PostgreSQL automatically.

The new online database starts empty. Your laptop's SQLite accounts and stock are not automatically transferred. The catalog is initialized automatically; no public demonstration accounts are published.

## 3. Import the repository into Vercel
Open https://vercel.com/new, connect GitHub and import `resilio`.

- Root Directory: the folder containing `manage.py` (leave at repository root if step 1 was followed).
- Let Vercel detect Django/Python. Do not select a static HTML preset or add a runserver start command.
- Leave Build Command at the project default. The included `pyproject.toml` already selects `python tools/vercel_build.py`.
- Keep Vercel's system environment variables enabled. Hostnames, HTTPS, secure cookies and production DEBUG=False are automatic.

Expand **Environment Variables** and add these for **Production**:

| Name | What you enter |
|---|---|
| `DATABASE_URL` | The PostgreSQL connection string from step 2 |
| `DJANGO_SECRET_KEY` | Double-click `generate-secret-windows.bat` in this package; copy the generated value |
| `RESILIO_ADMIN_USERNAME` | Your chosen online administrator username |
| `RESILIO_ADMIN_PASSWORD` | A new strong password, at least 12 characters |
| `RESILIO_ADMIN_EMAIL` | Your email (optional) |
| `DATABASE_URL_UNPOOLED` | Direct PostgreSQL connection string, if provided (optional) |

Do not paste these secrets into chat or GitHub. No need to set allowed hosts manually for the normal Vercel production URL.

Click **Deploy**. The build applies migrations, initializes the catalog, optionally creates your private administrator and lets Vercel collect static files automatically. It never resets an existing administrator password or promotes an existing public account with the same username.

## 4. Open and sign in
Open the successful production deployment URL. Choose **Sign in → Administrator** and use the credentials from step 3. Test a community signup, a request, an offer and a volunteer delivery. Try two browsers sharing presence on Live map.

After the first successful deploy, remove **both** `RESILIO_ADMIN_USERNAME` and `RESILIO_ADMIN_PASSWORD` from Vercel's Production environment settings (and the optional bootstrap email), then redeploy. Your saved administrator remains in PostgreSQL. Keep `DATABASE_URL` and `DJANGO_SECRET_KEY` permanently configured.

You do not need to leave VS Code or your laptop running for the hosted website.

## If a build fails
- `Set DJANGO_SECRET_KEY`: run the provided generator and save its complete value in Vercel, then redeploy.
- `Connect a PostgreSQL database`: check the exact `DATABASE_URL` name and full connection string. A file named db.sqlite3 cannot serve as the hosted database.
- `Bootstrap username already belongs...`: choose a new administrator username, or remove both bootstrap username/password if an administrator already exists.
- `Preview builds require...`: use a production deployment of `main`. Preview branches are blocked until you configure a separate preview database; the production database is never silently reused.
- Login/CSRF trouble on a custom domain: add the exact hostname to `DJANGO_ALLOWED_HOSTS` and `https://hostname` to `DJANGO_CSRF_TRUSTED_ORIGINS`, then redeploy.
- If a provider does not expose `DATABASE_URL` under that exact name, copy its PostgreSQL URL into that name yourself.

The package has not been deployed to your accounts. You still need to connect your own GitHub, Vercel and database accounts. `docs/VERCEL_TECHNICAL.md` contains validation details and advanced configuration.
