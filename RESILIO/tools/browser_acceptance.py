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
                    viewport={"width": 1440, "height": 1000},
                    color_scheme="dark",
                    geolocation={
                        "latitude": 23.8103,
                        "longitude": 90.4125,
                        "accuracy": 25,
                    },
                    permissions=["geolocation"],
                )
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(error.stack))
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
                page.wait_for_selector(".leaflet-container")
                page.wait_for_function(
                    "document.querySelector('#mapStatus').textContent.includes('boundaries loaded')"
                )
                page.get_by_role("button", name="Use my location", exact=True).click()
                page.wait_for_function(
                    "document.querySelector('#locationInfo').textContent.includes('23.810300')"
                )
                assert "Dhaka" in page.locator("#locationInfo").inner_text()
                assert page.evaluate(
                    "async()=>!(await(await fetch('/api/me/')).json()).user.share_location"
                )
                page.get_by_role("button", name="Share my pin", exact=True).click()
                page.locator("#actionForm [name=confirmation]").fill("SHARE")
                page.locator("#actionForm").get_by_role(
                    "button", name="Save on server", exact=True
                ).click()
                page.wait_for_function("!document.querySelector('#actionDialog').open")
                assert peer_page.evaluate(
                    "async()=> (await(await fetch('/api/presence/')).json()).participants.some(p=>p.location&&p.location.latitude==23.8103)"
                )
                page.locator(".map-geography-controls [name=division]").select_option(
                    "dhaka"
                )
                page.locator(".map-geography-controls [name=district]").select_option(
                    "dhaka"
                )
                page.wait_for_function(
                    "document.querySelector('.participant-list').textContent.includes('Relief Desk')"
                )
                page.get_by_role("button", name="All Bangladesh", exact=True).click()
                page.get_by_role(
                    "button", name="Stop sharing my pin", exact=True
                ).click()
                page.wait_for_function(
                    "document.querySelector('.map-footer-actions').textContent.includes('Share my pin')"
                )
                assert peer_page.evaluate(
                    "async()=> !(await(await fetch('/api/presence/')).json()).participants.some(p=>p.location)"
                )
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
                panel = page.locator(".bangladesh-panel")
                panel.locator("[name=division]").select_option("sylhet")
                assert panel.locator("[name=district] option").count() == 5
                panel.locator("[name=district]").select_option("sylhet")
                assert (
                    panel.locator(".participant-list h3").first.inner_text() == "Sylhet"
                )
                panel.get_by_role("button", name="All Bangladesh", exact=True).click()
                page.get_by_role("button", name="Use my location", exact=True).click()
                page.wait_for_function(
                    "document.querySelector('#locationInfo').textContent.includes('23.810300')"
                )
                context.set_geolocation(
                    {"latitude": 23.8203, "longitude": 90.4225, "accuracy": 40}
                )
                page.wait_for_function(
                    "document.querySelector('#locationInfo').textContent.includes('23.820300')"
                )
                assert peer_page.evaluate(
                    "async()=> !(await(await fetch('/api/presence/')).json()).participants.some(p=>p.location)"
                )
                context.set_offline(True)
                page.reload()
                page.wait_for_selector(".leaflet-container .leaflet-overlay-pane path")
                assert "64 districts" in page.locator(".participant-list").inner_text()
                context.set_offline(False)
                page.reload()
                page.wait_for_selector(".leaflet-container .leaflet-overlay-pane path")
                denied = browser.new_context(permissions=[])
                denied.grant_permissions([])
                denied_page = denied.new_page()
                denied_page.goto(url + "/#network")
                denied_page.wait_for_selector(".leaflet-container")
                denied_page.get_by_role(
                    "button", name="Use my location", exact=True
                ).click()
                denied_page.wait_for_function(
                    "document.querySelector('#mapStatus').textContent.includes('denied')"
                )
                denied_page.locator(
                    ".map-geography-controls [name=division]"
                ).select_option("khulna")
                denied_page.locator(
                    ".map-geography-controls [name=district]"
                ).select_option("jashore")
                assert (
                    denied_page.locator(".participant-list h3").first.inner_text()
                    == "Jashore"
                )
                denied.close()
                print(
                    "PASS district drilldown, real location updates, denied permission fallback and offline geographic map"
                )
                peer.close()
                print(
                    "PASS two-browser opt-in presence, opt-out, real geographic map and private device geolocation and private-cache isolation"
                )
                # Field coordination feature checks use the same isolated temporary server.
                navigate("overview")
                page.locator("[data-language-toggle]").click()
                page.wait_for_function("document.documentElement.lang==='bn'")
                assert (
                    page.locator('#navigation a[href="#emergencies"]').inner_text()
                    == "জরুরি সহায়তা"
                )
                page.reload()
                page.wait_for_function("document.documentElement.lang==='bn'")
                page.locator("[data-language-toggle]").click()
                page.wait_for_function("document.documentElement.lang==='en'")
                page.get_by_role("button", name="Offer supplies", exact=True).click()
                form = page.locator("#resourceForm")
                form.locator("[name=item]").select_option(label="Drinking water (L)")
                form.locator("[name=quantity]").fill("3")
                form.locator("[name=area]").fill("Test ward")
                form.locator("[name=district]").select_option("dhaka")
                upazila = (
                    form.locator("[name=upazila] option").nth(1).get_attribute("value")
                )
                form.locator("[name=upazila]").select_option(upazila)
                form.get_by_role("button", name="Choose on map", exact=True).click()
                page.locator(
                    "#pinDialog .leaflet-container .leaflet-overlay-pane path"
                ).first.wait_for()
                page.locator("#pinDialog .leaflet-container").click(
                    position={"x": 160, "y": 180}
                )
                page.locator("#pinDialog").get_by_role(
                    "button", name="Use selected point", exact=True
                ).click()
                page.wait_for_selector("#pinDialog", state="detached")
                form.locator("[name=latitude]").fill("23.810300")
                form.locator("[name=longitude]").fill("90.412500")
                form.locator("[name=pin_label]").fill("Test collection point")
                form.locator("[name=pin_consent]").check()
                form.get_by_role("button", name="Save on server", exact=True).click()
                page.wait_for_function("!document.querySelector('#editor').open")
                assert page.evaluate(
                    "async()=> (await(await fetch('/api/public/')).json()).offers.some(x=>x.pin?.label==='Test collection point')"
                )
                page.locator(".filter-bar [name=district]").select_option("dhaka")
                page.locator(".filter-bar [name=upazila]").select_option(upazila)
                assert page.locator(".resource-card").count() == 1
                page.locator(".filter-bar [name=upazila]").select_option("")
                page.locator(".filter-bar [name=division]").select_option("")
                navigate("shelters")
                page.get_by_role("button", name="Add shelter", exact=True).click()
                af = page.locator("#actionForm")
                af.locator("[name=name]").fill("Browser field shelter")
                af.locator("[name=area]").fill("Test ward")
                af.locator("[name=district]").select_option("dhaka")
                af.locator("[name=total]").fill("50")
                af.get_by_role("button", name="Save on server", exact=True).click()
                page.wait_for_function("!document.querySelector('#actionDialog').open")
                shelter = page.locator(".shelter-grid .panel").filter(
                    has_text="Browser field shelter"
                )
                shelter.get_by_role(
                    "button", name="Set shelter location", exact=True
                ).click()
                af.locator("[name=upazila]").select_option(upazila)
                af.locator("[name=latitude]").fill("23.8203")
                af.locator("[name=longitude]").fill("90.4225")
                af.locator("[name=pin_consent]").check()
                af.get_by_role("button", name="Save on server", exact=True).click()
                page.wait_for_function("!document.querySelector('#actionDialog').open")
                shelter.get_by_role(
                    "button", name="View exact pin", exact=True
                ).wait_for()
                navigate("network")
                page.get_by_role("button", name="Use my location", exact=True).click()
                page.wait_for_function(
                    "document.querySelector('#locationInfo').textContent.includes('23.820300')"
                )
                navigate("shelters")
                page.get_by_role("button", name="Sort by distance", exact=True).click()
                assert (
                    "km straight-line distance"
                    in page.locator(".shelter-grid").inner_text()
                )
                member_context = browser.new_context()
                member_page = member_context.new_page()
                member_page.on("pageerror", lambda error: errors.append(error.stack))
                member_page.goto(url + "/accounts/login/")
                member_page.locator("[name=username]").fill("demo_requester")
                member_page.locator("[name=password]").fill(password)
                member_page.get_by_role("button", name="Sign in", exact=True).click()
                member_page.wait_for_selector("#account:not([hidden])")
                member_page.locator('#navigation a[href="#emergencies"]').click()
                member_page.get_by_role(
                    "button", name="Request urgent assistance", exact=True
                ).click()
                mf = member_page.locator("#actionForm")
                mf.locator("[name=kind]").select_option("evacuation")
                mf.locator("[name=people]").fill("3")
                mf.locator("[name=area]").fill("Test ward")
                mf.locator("[name=description]").fill("Browser evacuation case")
                mf.locator("[name=contact]").fill("Private test contact")
                mf.locator("[name=latitude]").fill("23.8103")
                mf.locator("[name=longitude]").fill("90.4125")
                mf.locator("[name=pin_consent]").check()
                mf.get_by_role("button", name="Send emergency case", exact=True).click()
                member_page.wait_for_function(
                    "!document.querySelector('#actionDialog').open"
                )
                member_page.locator(".emergency-card").filter(
                    has_text="Browser evacuation case"
                ).wait_for()
                page.reload()
                page.wait_for_selector("#navigation")
                navigate("emergencies")
                case = page.locator(".emergency-card").filter(
                    has_text="Browser evacuation case"
                )
                case.get_by_role("button", name="Acknowledge", exact=True).click()
                case.get_by_role("button", name="Assign volunteer", exact=True).click()
                af.locator("[name=volunteer]").select_option(label="demo_volunteer")
                af.get_by_role("button", name="Save on server", exact=True).click()
                page.wait_for_function("!document.querySelector('#actionDialog').open")
                case.get_by_role("button", name="Mark resolved", exact=True).click()
                af.locator("[name=confirmation]").fill("RESOLVED")
                af.get_by_role("button", name="Save on server", exact=True).click()
                page.wait_for_function("!document.querySelector('#actionDialog').open")
                case.get_by_text("RESOLVED", exact=True).wait_for()
                assert page.evaluate(
                    "async()=>!JSON.stringify(await(await fetch('/api/public/')).json()).includes('Private test contact')"
                )
                navigate("announcements")
                page.get_by_role(
                    "button", name="Publish announcement", exact=True
                ).click()
                af.locator("[name=title]").fill("Browser announcement")
                af.locator("[name=body]").fill("Live map")
                af.locator("[name=expires_at]").fill(
                    (
                        __import__("datetime").datetime.now()
                        + __import__("datetime").timedelta(hours=2)
                    ).strftime("%Y-%m-%dT%H:%M")
                )
                af.get_by_role("button", name="Save on server", exact=True).click()
                page.wait_for_function("!document.querySelector('#actionDialog').open")
                page.locator("[data-language-toggle]").click()
                page.wait_for_function("document.documentElement.lang==='bn'")
                page.locator("[data-user-content]").filter(
                    has_text="Live map"
                ).wait_for()
                page.locator("[data-language-toggle]").click()
                navigate("activity")
                page.get_by_role(
                    "button", name="Assignment messages", exact=True
                ).first.click()
                af.locator("[name=body]").fill("Browser private assignment message")
                af.get_by_role("button", name="Send message", exact=True).click()
                page.locator(".thread-message").filter(
                    has_text="Browser private assignment message"
                ).wait_for()
                page.locator("[data-close=actionDialog]").click()
                member_page.locator('#navigation a[href="#activity"]').click()
                member_page.get_by_role(
                    "button", name="Assignment messages", exact=True
                ).first.click()
                member_page.locator(".thread-message").filter(
                    has_text="Browser private assignment message"
                ).wait_for()
                member_context.close()
                navigate("sync")
                page.locator(".offline-readiness").get_by_text(
                    "Boundary map saved for offline use", exact=True
                ).wait_for()
                assert page.evaluate(
                    "async()=>{for(const k of await caches.keys()){for(const r of await(await caches.open(k)).keys()){if(new URL(r.url).pathname.startsWith('/api/'))return false}}return true}"
                )
                print(
                    "PASS field pins, nested map picker, upazila filtering, Bangla persistence, private emergency lifecycle, announcements, assignment messages and offline readiness"
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
                            "network",
                            "emergencies",
                            "announcements",
                            "activity",
                            "volunteer",
                            "shelters",
                            "notifications",
                            "sync",
                            "administration",
                            "profile",
                        ]:
                            navigate(screen)
                            if not page.evaluate(
                                "document.documentElement.scrollWidth<=innerWidth"
                            ):
                                print(
                                    "OVERFLOW",
                                    width,
                                    theme,
                                    screen,
                                    page.evaluate(
                                        "[...document.querySelectorAll('main *')].filter(e=>e.getBoundingClientRect().right>innerWidth+1).slice(0,8).map(e=>[e.tagName,e.className,e.textContent.slice(0,80)])"
                                    ),
                                )
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
                for width in [1440, 390]:
                    page.set_viewport_size({"width": width, "height": 1000})
                    page.locator("[data-language-toggle]").click()
                    page.wait_for_function("document.documentElement.lang==='bn'")
                    for screen in ["emergencies", "announcements", "sync", "network"]:
                        navigate(screen)
                        page.evaluate("document.fonts.ready")
                        assert page.evaluate(
                            "document.documentElement.scrollWidth<=innerWidth"
                        ), ("Bangla", width, screen)
                        if os.getenv("RESILIO_QA_SCREENSHOTS"):
                            shots = Path(os.environ["RESILIO_QA_SCREENSHOTS"])
                            shots.mkdir(parents=True, exist_ok=True)
                            page.screenshot(
                                path=str(shots / f"field-{width}-bn-{screen}.png"),
                                full_page=True,
                            )
                    page.locator("[data-language-toggle]").click()
                    page.wait_for_function("document.documentElement.lang==='en'")
                print("PASS Bangla field screens, local font loading and mobile layout")
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
                            navigate("network")
                            page.wait_for_selector(
                                ".leaflet-container .leaflet-overlay-pane path"
                            )
                            page.screenshot(
                                path=str(shots / f"{label}-{theme}-map.png"),
                                full_page=True,
                            )
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
