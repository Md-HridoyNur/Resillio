"""Reproduce the separate-process SQLite persistence check without touching real data."""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

base = Path(__file__).resolve().parents[1]
with tempfile.TemporaryDirectory(prefix="resilio-persistence-") as tmp:
    env = {**os.environ, "RESILIO_DB": str(Path(tmp) / "test.sqlite3")}

    def run(*args):
        return subprocess.run(
            [sys.executable, "manage.py", *args],
            cwd=base,
            env=env,
            check=True,
            capture_output=True,
            text=True,
        )

    run("migrate", "--noinput")
    run(
        "shell",
        "-c",
        "from django.contrib.auth.models import User; from coordination.models import Category,Item,Offer; u=User.objects.create_user('persistence_test'); c,_=Category.objects.get_or_create(name='water'); i,_=Item.objects.get_or_create(name='Drinking water',defaults={'unit':'L','category':c}); Offer.objects.create(owner=u,item=i,quantity=50,area='mirpur')",
    )
    run(
        "shell",
        "-c",
        "from coordination.models import Offer; assert Offer.objects.get().quantity==50",
    )
    print("PASS: inventory survived a fresh Python/Django process.")
