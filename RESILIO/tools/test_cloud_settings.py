"""Subprocess checks for deployment configuration. No hosted credentials required."""

import json, os, subprocess, sys, tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
KEY = "Test-only-" + ("abcXYZ092_" * 7)
SCRIPT = "from config import settings as s; import json; print(json.dumps({'debug':s.DEBUG,'db':s.DATABASES['default']['ENGINE'],'hosts':s.ALLOWED_HOSTS,'origins':s.CSRF_TRUSTED_ORIGINS,'secure':getattr(s,'SESSION_COOKIE_SECURE',False),'ssl':s.DATABASES['default'].get('OPTIONS',{}).get('sslmode'),'name':s.DATABASES['default']['NAME']}))"
base = {
    k: v
    for k, v in os.environ.items()
    if not k.startswith(("VERCEL", "RESILIO", "DJANGO", "DATABASE_URL"))
}


def check(env, success=True):
    r = subprocess.run(
        [sys.executable, "-c", SCRIPT],
        cwd=ROOT,
        env={**base, **env},
        capture_output=True,
        text=True,
    )
    assert (r.returncode == 0) == success, r.stderr
    return json.loads(r.stdout) if success else r.stderr


local = check({})
assert local["db"].endswith("sqlite3")
prod = {
    "VERCEL": "1",
    "VERCEL_ENV": "production",
    "VERCEL_URL": "resilio-build-example.vercel.app",
    "VERCEL_PROJECT_PRODUCTION_URL": "resilio-example.vercel.app",
    "DJANGO_SECRET_KEY": KEY,
    "DATABASE_URL": "postgresql://test:test@localhost:5432/resilio",
}
s = check(prod)
assert not s["debug"] and s["secure"] and s["ssl"] == "require"
assert s["hosts"] == ["resilio-build-example.vercel.app", "resilio-example.vercel.app"]
assert "https://resilio-example.vercel.app" in s["origins"]
assert "DJANGO_SECRET_KEY" in check({**prod, "DJANGO_SECRET_KEY": ""}, False)
assert "DATABASE_URL" in check({**prod, "DATABASE_URL": ""}, False)
assert "PostgreSQL" in check({**prod, "DATABASE_URL": "sqlite:///test.sqlite3"}, False)
assert "Preview" in check({**prod, "VERCEL_ENV": "preview"}, False)
preview = check(
    {
        **prod,
        "VERCEL_ENV": "preview",
        "RESILIO_PREVIEW_DATABASE_URL": "postgresql://test:test@localhost:5432/preview_isolated",
    }
)
assert preview["name"] == "preview_isolated"
assert check({**prod, "DJANGO_ALLOWED_HOSTS": "*"}, False)
assert check({**prod, "RESILIO_DEBUG": "1"}, False)
print(
    "PASS: local fallback, PostgreSQL URL, HTTPS cookies/SSL, exact automatic hosts/origins, missing secrets/database rejection, SQLite refusal, preview isolation and debug/wildcard rejection."
)
