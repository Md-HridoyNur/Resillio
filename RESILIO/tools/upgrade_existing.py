"""Install this release into an existing RESILIO folder without replacing local data.
Stop runserver first. A backup is created before any source file is replaced.
"""

import argparse
import datetime
import shutil
import sqlite3
import subprocess
from pathlib import Path

SOURCE = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".venv", "__pycache__", "node_modules", "staticfiles", ".git"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--target", required=True, help="Existing RESILIO folder containing manage.py"
    )
    args = parser.parse_args()
    target = Path(args.target.strip().strip('"')).expanduser().resolve()
    if target == SOURCE:
        parser.error("Select your OLD project folder, not this newly extracted folder.")
    if (
        not (target / "manage.py").is_file()
        or not (target / "config/settings.py").is_file()
    ):
        parser.error("The target must be your existing RESILIO project folder.")
    backup = target.parent / (
        "RESILIO-backup-" + datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    backup.mkdir(exist_ok=False)
    # sqlite backup gives a consistent copy even if a reader has the database open.
    for path in target.rglob("*"):
        rel = path.relative_to(target)
        if not path.is_file() or set(rel.parts) & SKIP_DIRS:
            continue
        if ".sqlite3-" in path.name:
            continue
        output = backup / rel
        output.parent.mkdir(parents=True, exist_ok=True)
        if path.name.endswith(".sqlite3"):
            with sqlite3.connect(path) as old, sqlite3.connect(output) as saved:
                old.backup(saved)
        else:
            shutil.copy2(path, output)
    for path in SOURCE.rglob("*"):
        rel = path.relative_to(SOURCE)
        if not path.is_file() or set(rel.parts) & SKIP_DIRS:
            continue
        if (
            path.name in [".local-secret", ".env"]
            or ".sqlite3" in path.name
            or path.suffix == ".pyc"
        ):
            continue
        destination = target / rel
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, destination)
    python = (
        target
        / ".venv"
        / ("Scripts/python.exe" if __import__("os").name == "nt" else "bin/python")
    )
    print("Backup:", backup)
    print("Updated code:", target)
    if python.exists():
        subprocess.run(
            [str(python), "-m", "pip", "install", "-r", "requirements.txt"],
            cwd=target,
            check=True,
        )
        subprocess.run(
            [str(python), "manage.py", "migrate", "--noinput"], cwd=target, check=True
        )
        subprocess.run(
            [str(python), "manage.py", "initialize_catalog"], cwd=target, check=True
        )
        print("Upgrade complete. Your accounts, passwords and database were preserved.")
        print(
            "Start with the same manage.py runserver command. Reload the browser after the new assets install."
        )
    else:
        print(
            "Source updated. Run start-windows.bat (or start-unix.sh) in the existing folder to install dependencies and migrate."
        )


if __name__ == "__main__":
    main()
