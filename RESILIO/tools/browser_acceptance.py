"""Optional real-browser acceptance suite. Uses its own temporary SQLite database.
Install playwright separately, then `python -m playwright install chromium`.
CHROMIUM_PATH may point at an existing compatible Chrome/Chromium binary.
The application itself requires no browser automation dependencies.
"""

import os, sys, tempfile, subprocess, threading, json
from pathlib import Path

BASE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BASE))


def main():
    from playwright.sync_api import sync_playwright

    with tempfile.TemporaryDirectory(prefix="resilio-browser-") as tmp:
        os.environ["RESILIO_DB"] = str(Path(tmp) / "browser.sqlite3")
        os.environ["DJANGO_SETTINGS_MODULE"] = "config.settings"
        os.environ["DJANGO_ALLOWED_HOSTS"] = "localhost,127.0.0.1"
        password = "Browser-Fictional!2026"
        subprocess.run(
            [sys.executable, "manage.py", "migrate", "--noinput"],
            cwd=BASE,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        subprocess.run(
            [sys.executable, "manage.py", "seed_demo", "--password", password],
            cwd=BASE,
            check=True,
            stdout=subprocess.DEVNULL,
        )
        import django

        django.setup()
        from django.contrib.auth.models import User

        User.objects.create_superuser(
            "demo_admin", password=password, email="admin@example.invalid"
        )
        from django.core.wsgi import get_wsgi_application
        from django.contrib.staticfiles.handlers import StaticFilesHandler
        from wsgiref.simple_server import make_server, WSGIRequestHandler

        class Quiet(WSGIRequestHandler):
            def log_message(self, *args):
                pass

        server = make_server(
            "127.0.0.1",
            0,
            StaticFilesHandler(get_wsgi_application()),
            handler_class=Quiet,
        )
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f"http://127.0.0.1:{server.server_port}"
        try:
            with sync_playwright() as pw:
                options = {"headless": True, "args": ["--no-sandbox"]}
                if os.getenv("CHROMIUM_PATH"):
                    options["executable_path"] = os.environ["CHROMIUM_PATH"]
                browser = pw.chromium.launch(**options)
                context = browser.new_context(
                    viewport={"width": 1440, "height": 1000}, color_scheme="dark"
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(url)
                page.wait_for_selector(".resource-card")
                assert page.locator("html").get_attribute("data-theme") == "dark"
                page.get_by_role(
                    "button", name="Current theme: dark. Switch theme", exact=True
                ).click()
                page.reload()
                page.wait_for_selector(".resource-card")
                assert page.locator("html").get_attribute("data-theme") == "light"
                page.emulate_media(color_scheme="dark")
                assert page.locator("html").get_attribute("data-theme") == "light"
                page.get_by_role("button", name="Use device theme", exact=True).click()
                assert page.locator("html").get_attribute("data-theme") == "dark"
                page.emulate_media(color_scheme="light")
                page.wait_for_function(
                    "document.documentElement.dataset.theme==='light'"
                )
                print("PASS browser theme switching, persistence and system changes")

                def login(username):
                    page.goto(url + "/accounts/login/")
                    page.locator("[name=username]").fill(username)
                    page.locator("[name=password]").fill(password)
                    page.get_by_role("button", name="Sign in", exact=True).click()
                    page.wait_for_function(
                        "document.querySelector('#account')?.textContent.includes('demo_')"
                    )

                def navigate(hash):
                    page.locator(f'#navigation a[href="#{hash}"]').click()
                    page.wait_for_timeout(100)

                login("demo_volunteer")
                need = page.locator(".resource-card.request").filter(
                    has_text="Drinking water"
                )
                need.get_by_role("button", name="View compatible offers").click()
                page.locator("#actionDialog").get_by_role(
                    "button", name="Reserve supply"
                ).click()
                page.wait_for_function("!document.querySelector('#actionDialog').open")
                navigate("volunteer")
                page.get_by_role("button", name="Start delivery").click()
                page.get_by_role("button", name="Submit delivered quantity").click()
                page.locator("#actionForm [name=quantity]").fill("20")
                page.locator("#actionForm").get_by_role(
                    "button", name="Save on server"
                ).click()
                page.wait_for_function("!document.querySelector('#actionDialog').open")
                page.get_by_role("button", name="Sign out", exact=True).click()
                page.wait_for_function(
                    "document.querySelector('#account')?.textContent==='Public access'"
                )
                login("demo_requester")
                navigate("activity")
                page.get_by_role("button", name="Confirm receipt").click()
                page.locator("#actionForm [name=confirmation]").fill("RECEIVED")
                page.locator("#actionForm").get_by_role(
                    "button", name="Save on server"
                ).click()
                page.wait_for_function("!document.querySelector('#actionDialog').open")
                import sqlite3

                check_db = sqlite3.connect(os.environ["RESILIO_DB"])
                assert (
                    check_db.execute(
                        "SELECT status FROM coordination_helprequest WHERE demo=1"
                    ).fetchone()[0]
                    == "fulfilled"
                )
                confirmed = check_db.execute(
                    "SELECT SUM(quantity) FROM coordination_delivery"
                ).fetchone()[0]
                offered = check_db.execute(
                    "SELECT quantity FROM coordination_offer JOIN coordination_item ON coordination_offer.item_id=coordination_item.id WHERE coordination_item.name='Drinking water'"
                ).fetchone()[0]
                assert offered - confirmed == 30
                assert (
                    check_db.execute(
                        "SELECT COUNT(*) FROM coordination_delivery"
                    ).fetchone()[0]
                    == 1
                )
                navigate("overview")
                page.wait_for_selector(".resource-card")
                assert (
                    "30 L"
                    in page.locator(".resource-card.offer")
                    .filter(has_text="Drinking water")
                    .inner_text()
                )
                print("PASS real browser 20 L full workflow and 30 L remaining supply")
                page.evaluate("navigator.serviceWorker.ready")
                page.reload()
                page.wait_for_selector(".resource-card")
                page.wait_for_function("!!navigator.serviceWorker.controller")
                context.set_offline(True)
                page.get_by_role(
                    "button", name="+ Request assistance", exact=True
                ).click()
                page.locator("#resourceForm [name=quantity]").fill("5")
                page.locator("#resourceForm [name=area]").fill("uttara")
                page.get_by_role("button", name="Save request on device").click()
                page.wait_for_function("!document.querySelector('#editor').open")
                navigate("sync")
                page.wait_for_selector("text=Pending sync")
                page.reload()
                page.wait_for_selector("text=Pending sync")
                assert "Last successful sync:" in page.locator("#status").inner_text()
                print(
                    "PASS offline navigation reload via service worker and IndexedDB pending queue"
                )
                context.set_offline(False)
                page.reload()
                page.wait_for_selector("text=Retry synchronization")
                page.get_by_role("button", name="Retry synchronization").click()
                page.wait_for_selector("text=Confirmed server request #")
                before = check_db.execute(
                    "SELECT COUNT(*) FROM coordination_helprequest"
                ).fetchone()[0]
                page.get_by_role("button", name="Verify same server ID").click()
                page.wait_for_timeout(200)
                assert (
                    check_db.execute(
                        "SELECT COUNT(*) FROM coordination_helprequest"
                    ).fetchone()[0]
                    == before
                )
                print("PASS offline-to-online sync and duplicate-safe retry")
                page.get_by_role("button", name="Sign out", exact=True).click()
                page.wait_for_function(
                    "document.querySelector('#account')?.textContent==='Public access'"
                )
                page.goto(url + "/access/")
                assert page.locator(".portal-stack .portal-card").count() == 3
                page.goto(url + "/register/?role=coordinator")
                page.locator("[name=username]").fill("browser_officer")
                page.locator("[name=organization]").fill("Browser Relief NGO")
                page.locator("[name=area]").fill("Mirpur")
                page.locator("[name=password1]").fill(password)
                page.locator("[name=password2]").fill(password)
                page.get_by_role("button", name="Create account", exact=True).click()
                page.wait_for_selector("#account:not([hidden])")
                navigate("coordination")
                assert (
                    "awaiting administrator approval"
                    in page.locator("#screen").inner_text()
                )
                page.get_by_role("button", name="Sign out", exact=True).click()
                page.wait_for_function(
                    "document.querySelector('#account')?.textContent==='Public access'"
                )
                login("demo_admin")
                navigate("administration")
                approval = page.locator(".approval-card").filter(
                    has_text="Browser Relief NGO"
                )
                approval.get_by_role(
                    "button", name="Approve officer", exact=True
                ).click()
                page.locator("#actionForm [name=confirmation]").fill("APPROVE")
                page.locator("#actionForm").get_by_role(
                    "button", name="Save on server", exact=True
                ).click()
                page.wait_for_function("!document.querySelector('#actionDialog').open")
                page.locator(".approval-card").filter(
                    has_text="Browser Relief NGO"
                ).get_by_text("Approved officer", exact=False).wait_for()
                print(
                    "PASS three access portals, officer application and administrator approval"
                )
                navigate("overview")
                page.get_by_role("button", name="Share my presence", exact=True).click()
                page.locator("#actionForm [name=label]").fill("Relief Desk")
                page.locator("#actionForm").get_by_role(
                    "button", name="Save on server", exact=True
                ).click()
                page.wait_for_function("!document.querySelector('#actionDialog').open")
                peer = browser.new_context()
                peer_page = peer.new_page()
                peer_page.goto(url + "/accounts/login/?portal=volunteer")
                peer_page.locator("[name=username]").fill("demo_volunteer")
                peer_page.locator("[name=password]").fill(password)
                peer_page.get_by_role("button", name="Sign in", exact=True).click()
                peer_page.wait_for_selector("#account:not([hidden])")
                peer_page.get_by_role(
                    "button", name="Share my presence", exact=True
                ).click()
                peer_page.locator("#actionForm [name=label]").fill("Field Team")
                peer_page.locator("#actionForm").get_by_role(
                    "button", name="Save on server", exact=True
                ).click()
                peer_page.wait_for_function(
                    "!document.querySelector('#actionDialog').open"
                )
                navigate("network")
                page.wait_for_selector('.participant-row:has-text("Field Team")')
                assert "Relief Desk" in page.locator(".participant-list").inner_text()
                page.get_by_role("button", name="Demo animation", exact=True).click()
                page.wait_for_function(
                    "document.querySelector('#mapStatus').textContent.includes('SIMULATION')"
                )
                first = page.locator("#coordinationMap").evaluate("(c)=>c.toDataURL()")
                page.wait_for_timeout(250)
                assert (
                    page.locator("#coordinationMap").evaluate("(c)=>c.toDataURL()")
                    != first
                )
                page.get_by_role("button", name="Live activity", exact=True).click()
                peer_page.get_by_role(
                    "button", name="Stop sharing my presence", exact=True
                ).click()
                peer_page.wait_for_selector('button:has-text("Share my presence")')
                page.reload()
                page.wait_for_selector(".participant-list")
                page.wait_for_function(
                    "document.querySelector('.participant-list').textContent.includes('Relief Desk')"
                )
                assert (
                    "Field Team" not in page.locator(".participant-list").inner_text()
                )
                assert page.evaluate(
                    "async()=>{for(const k of await caches.keys()){for(const r of await (await caches.open(k)).keys()){if(new URL(r.url).pathname.startsWith('/api/'))return false}}return true}"
                )
                peer.close()
                print(
                    "PASS two-browser opt-in presence, opt-out, moving simulation and private-cache isolation"
                )
                for width in [1440, 390]:
                    page.set_viewport_size({"width": width, "height": 900})
                    for theme in ["dark", "light"]:
                        page.evaluate(
                            "theme=>{localStorage.setItem('resilio-theme',theme);location.reload()}",
                            theme,
                        )
                        page.wait_for_load_state("load")
                        page.wait_for_selector("#navigation")
                        for screen in [
                            "overview",
                            "activity",
                            "volunteer",
                            "shelters",
                            "notifications",
                            "sync",
                            "administration",
                            "profile",
                        ]:
                            navigate(screen)
                            assert page.evaluate(
                                "document.documentElement.scrollWidth<=innerWidth"
                            ), (width, theme, screen)
                        navigate("overview")
                        page.get_by_role("button", name="⚠ Crisis mode").click()
                        assert page.locator("#crisis").is_visible()
                        page.keyboard.press("Escape")
                        assert not page.locator("#crisis").is_visible()
                        page.get_by_role(
                            "button", name="+ Request assistance", exact=True
                        ).click()
                        assert page.locator("#editor").is_visible()
                        for _ in range(10):
                            page.keyboard.press("Tab")
                            assert page.evaluate(
                                "!!document.activeElement.closest('#editor')"
                            )
                        page.keyboard.press("Escape")
                        assert not page.locator("#editor").is_visible()
                if os.getenv("RESILIO_QA_SCREENSHOTS"):
                    shots = Path(os.environ["RESILIO_QA_SCREENSHOTS"])
                    shots.mkdir(parents=True, exist_ok=True)
                    for width, label in [(1440, "desktop"), (390, "mobile")]:
                        page.set_viewport_size({"width": width, "height": 1000})
                        navigate("overview")
                        for theme in ["dark", "light"]:
                            page.evaluate(
                                "theme=>{localStorage.setItem('resilio-theme',theme);location.reload()}",
                                theme,
                            )
                            page.wait_for_load_state("load")
                            page.wait_for_selector(".resource-card")
                            page.screenshot(
                                path=str(shots / f"{label}-{theme}.png"), full_page=True
                            )
                            page.get_by_role("button", name="⚠ Crisis mode").click()
                            page.screenshot(
                                path=str(shots / f"{label}-{theme}-crisis.png")
                            )
                            page.keyboard.press("Escape")
                            page.get_by_role(
                                "button", name="+ Request assistance", exact=True
                            ).click()
                            page.screenshot(
                                path=str(shots / f"{label}-{theme}-form.png")
                            )
                            page.keyboard.press("Escape")
                            navigate("administration")
                            page.screenshot(
                                path=str(shots / f"{label}-{theme}-admin.png"),
                                full_page=True,
                            )
                            navigate("overview")
                if os.getenv("RESILIO_QA_SCREENSHOTS"):
                    shots = Path(os.environ["RESILIO_QA_SCREENSHOTS"])
                    for width, label in [(1440, "desktop"), (390, "mobile")]:
                        page.set_viewport_size({"width": width, "height": 1000})
                        for theme in ["light", "dark"]:
                            page.goto(url + "/access/")
                            page.evaluate(
                                "theme=>localStorage.setItem('resilio-theme',theme)",
                                theme,
                            )
                            for route, name in [
                                ("/access/", "access"),
                                ("/accounts/login/?portal=coordinator", "login"),
                                ("/register/?role=coordinator", "register"),
                            ]:
                                page.goto(url + route)
                                assert page.evaluate(
                                    "document.documentElement.scrollWidth<=innerWidth"
                                ), (width, theme, name)
                                page.screenshot(
                                    path=str(shots / f"{label}-{theme}-{name}.png"),
                                    full_page=True,
                                )
                check_db.close()
                assert not errors, errors
                print(
                    "PASS desktop/mobile overflow, both themes, crisis Escape and no page errors"
                )
                browser.close()
        finally:
            server.shutdown()
            server.server_close()


if __name__ == "__main__":
    main()
