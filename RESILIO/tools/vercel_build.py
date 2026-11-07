"""Vercel build hook: migrate with a direct DB connection, initialize catalog,
optionally bootstrap a private admin, and leave static collection to Vercel.
"""

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
if os.getenv("VERCEL") == "1":
    preview = os.getenv("VERCEL_ENV") == "preview"
    if preview:
        direct = os.getenv("RESILIO_PREVIEW_DATABASE_URL_UNPOOLED")
        if direct:
            os.environ["RESILIO_PREVIEW_DATABASE_URL"] = direct
    elif os.getenv("DATABASE_URL_UNPOOLED"):
        os.environ["DATABASE_URL"] = os.environ["DATABASE_URL_UNPOOLED"]
import django

django.setup()
from django.core.management import call_command

call_command("migrate", interactive=False, verbosity=1)
call_command("initialize_catalog")
if os.getenv("VERCEL_ENV") != "preview":
    call_command("bootstrap_cloud_admin")
print("RESILIO database setup complete. Static collection is handled by Vercel.")
