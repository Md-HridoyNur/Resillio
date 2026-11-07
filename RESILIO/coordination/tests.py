import json, uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from decimal import Decimal
from django.test import TestCase, TransactionTestCase, Client
from django.contrib.auth.models import User
from django.db import connection, close_old_connections, IntegrityError, transaction
from django.utils import timezone
from .models import *


class Fixtures:
    def setup_data(self):
        CoordinationLock.objects.get_or_create(pk=1)
        self.member = User.objects.create_user("member", password="Coursework-Pass!47")
        self.donor = User.objects.create_user("donor", password="Coursework-Pass!47")
        self.vol = User.objects.create_user("vol", password="Coursework-Pass!47")
        self.other = User.objects.create_user("other", password="Coursework-Pass!47")
        self.admin = User.objects.create_user(
            "ops", password="Coursework-Pass!47", is_staff=True
        )
        Profile.objects.create(user=self.vol, role="volunteer")
        self.category = Category.objects.create(name="water")
        self.water = Item.objects.create(
            name="Drinking water", unit="L", category=self.category
        )
        self.tablets = Item.objects.create(
            name="Purification tablets", unit="tablets", category=self.category
        )
        self.offer = Offer.objects.create(
            owner=self.donor, item=self.water, quantity=50, area="mirpur"
        )
        self.need = HelpRequest.objects.create(
            owner=self.member, item=self.water, quantity=20, area="mirpur"
        )

    def post(self, user, action, data):
        client = Client()
        client.force_login(user)
        return client.post(
            "/api/" + action + "/",
            data=json.dumps(data),
            content_type="application/json",
        )

    def allocation(self, n=20):
        response = self.post(
            self.vol,
            "reserve",
            {"offer": self.offer.pk, "request": self.need.pk, "quantity": n},
        )
        self.assertEqual(response.status_code, 200, response.content)
        return response.json()["id"]

    def move(self, id, transition, user=None, quantity=None):
        return self.post(
            user or self.vol,
            "transition",
            {"id": id, "transition": transition, "quantity": quantity},
        )

    def finish(self, id, n):
        self.assertEqual(self.move(id, "start").status_code, 200)
        self.assertEqual(self.move(id, "submit", quantity=n).status_code, 200)
        self.assertEqual(self.move(id, "confirm", self.member).status_code, 200)


class Workflows(Fixtures, TestCase):
    def setUp(self):
        self.setup_data()

    def test_auth_registration_and_permissions(self):
        self.assertEqual(
            Client()
            .post("/api/resource/", {}, content_type="application/json")
            .status_code,
            401,
        )
        response = self.client.post(
            "/register/",
            {
                "username": "new",
                "password1": "Unique-Testing-Pass!87",
                "password2": "Unique-Testing-Pass!87",
                "role": "volunteer",
                "is_staff": "1",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(User.objects.get(username="new").is_staff)
        self.assertEqual(
            self.post(
                self.member,
                "reserve",
                {"offer": self.offer.pk, "request": self.need.pk, "quantity": 1},
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                self.other, "cancel", {"kind": "offer", "id": self.offer.pk}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                self.other, "shelter", {"name": "Hall", "area": "mirpur", "total": 10}
            ).status_code,
            403,
        )

    def test_csrf_enforced(self):
        c = Client(enforce_csrf_checks=True)
        c.force_login(self.member)
        self.assertEqual(
            c.post("/api/resource/", {}, content_type="application/json").status_code,
            403,
        )

    def test_resource_validation_normalization_edit_cancel(self):
        data = {
            "kind": "request",
            "item": self.water.pk,
            "quantity": 4,
            "area": "  MIRPUR   North  ",
            "description": "<script>alert(1)</script>",
        }
        result = self.post(self.member, "resource", data)
        self.assertEqual(result.status_code, 200)
        row = HelpRequest.objects.get(pk=result.json()["id"])
        self.assertEqual(row.area, "mirpur north")
        data["id"] = row.pk
        data["quantity"] = 5
        self.assertEqual(self.post(self.other, "resource", data).status_code, 403)
        self.assertEqual(self.post(self.member, "resource", data).status_code, 200)
        data["quantity"] = "NaN"
        self.assertEqual(self.post(self.member, "resource", data).status_code, 400)
        data["quantity"] = 0
        self.assertEqual(self.post(self.member, "resource", data).status_code, 400)
        self.assertEqual(
            self.post(
                self.member, "cancel", {"kind": "request", "id": row.pk}
            ).status_code,
            200,
        )
        row.refresh_from_db()
        self.assertEqual(row.status, "cancelled")

    def test_compatibility_expiry_and_match_explanations(self):
        other = Offer.objects.create(
            owner=self.donor, item=self.tablets, quantity=100, area="mirpur"
        )
        self.assertEqual(
            self.post(
                self.vol,
                "reserve",
                {"offer": other.pk, "request": self.need.pk, "quantity": 1},
            ).status_code,
            400,
        )
        self.client.force_login(self.vol)
        response = self.client.get("/api/matches/", {"request": self.need.pk})
        self.assertIn("Same area", response.json()["matches"][0]["reasons"])
        self.offer.expires_at = timezone.now() - timedelta(seconds=1)
        self.offer.save()
        self.assertEqual(self.offer.available, 0)
        self.assertEqual(
            self.client.get("/api/matches/", {"request": self.need.pk}).json()[
                "matches"
            ],
            [],
        )
        self.assertEqual(
            self.post(
                self.vol,
                "reserve",
                {"offer": self.offer.pk, "request": self.need.pk, "quantity": 1},
            ).status_code,
            400,
        )

    def test_acceptance_full_delivery_and_duplicate_confirm(self):
        id = self.allocation()
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.available, Decimal(30))
        self.assertEqual(self.need.unallocated, 0)
        self.finish(id, 20)
        self.need.refresh_from_db()
        self.offer.refresh_from_db()
        self.assertEqual(self.need.status, "fulfilled")
        self.assertEqual(self.offer.available, 30)
        self.assertEqual(self.move(id, "confirm", self.member).status_code, 400)
        self.assertEqual(Delivery.objects.count(), 1)
        result = self.client.get("/api/public/").json()
        self.assertEqual(result["stats"]["deliveries"], 1)
        self.assertEqual(
            next(r for r in result["offers"] if r["id"] == self.offer.pk)["available"],
            "30.00",
        )

    def test_partial_delivery_releases_unused_and_more_than_one_offer(self):
        id = self.allocation()
        self.finish(id, 12)
        self.need.refresh_from_db()
        self.assertEqual(self.need.status, "open")
        self.assertEqual(self.need.unallocated, 8)
        self.assertEqual(self.offer.available, 38)
        another = Offer.objects.create(
            owner=self.donor, item=self.water, quantity=8, area="uttara"
        )
        response = self.post(
            self.vol,
            "reserve",
            {"offer": another.pk, "request": self.need.pk, "quantity": 8},
        )
        self.finish(response.json()["id"], 8)
        self.need.refresh_from_db()
        self.assertEqual(self.need.status, "fulfilled")

    def test_one_offer_multiple_requests_and_cancel_release(self):
        id = self.allocation(10)
        need2 = HelpRequest.objects.create(
            owner=self.other, item=self.water, quantity=10, area="mirpur"
        )
        self.assertEqual(
            self.post(
                self.vol,
                "reserve",
                {"offer": self.offer.pk, "request": need2.pk, "quantity": 10},
            ).status_code,
            200,
        )
        self.assertEqual(self.offer.available, 30)
        self.assertEqual(self.move(id, "cancel").status_code, 200)
        self.assertEqual(self.offer.available, 40)
        self.assertEqual(self.need.unallocated, 20)

    def test_allocated_record_edits_and_cancellation_blocked(self):
        self.allocation(10)
        self.assertEqual(
            self.post(
                self.member,
                "resource",
                {
                    "kind": "request",
                    "id": self.need.pk,
                    "item": self.water.pk,
                    "quantity": 30,
                    "area": "mirpur",
                },
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post(
                self.donor, "cancel", {"kind": "offer", "id": self.offer.pk}
            ).status_code,
            400,
        )

    def test_over_reservation_transition_and_actor_restrictions(self):
        self.assertEqual(
            self.post(
                self.vol,
                "reserve",
                {"offer": self.offer.pk, "request": self.need.pk, "quantity": 21},
            ).status_code,
            400,
        )
        id = self.allocation(10)
        self.assertEqual(self.move(id, "submit", quantity=5).status_code, 400)
        self.assertEqual(self.move(id, "start", self.other).status_code, 403)
        self.move(id, "start")
        self.assertEqual(self.move(id, "submit", quantity=11).status_code, 400)
        self.move(id, "submit", quantity=5)
        self.assertEqual(self.move(id, "confirm", self.donor).status_code, 403)
        self.assertEqual(self.move(id, "cancel").status_code, 400)
        self.assertEqual(self.move(id, "confirm", self.admin).status_code, 200)

    def test_notifications_private_and_read_isolated(self):
        self.allocation()
        note = Notification.objects.filter(user=self.member).first()
        self.post(self.other, "read", {"id": note.pk})
        note.refresh_from_db()
        self.assertFalse(note.read)
        self.client.force_login(self.other)
        self.assertEqual(self.client.get("/api/me/").json()["notifications"], [])
        self.post(self.member, "read", {"id": note.pk})
        note.refresh_from_db()
        self.assertTrue(note.read)
        public = self.client.get("/api/public/").json()
        self.assertNotIn("notifications", public)
        self.assertNotIn("owner", public["requests"][0])

    def test_report_review_audit_and_no_auto_removal(self):
        report = self.post(
            self.member,
            "report",
            {"kind": "offer", "id": self.offer.pk, "reason": "Duplicate"},
        ).json()["id"]
        self.assertEqual(Offer.objects.get(pk=self.offer.pk).status, "open")
        self.assertEqual(
            self.post(
                self.other, "review", {"id": report, "decision": "Reviewed"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                self.admin, "review", {"id": report, "decision": "Verified; keep post"}
            ).status_code,
            200,
        )
        self.assertTrue(
            Notification.objects.filter(
                user=self.member, text__contains="reviewed"
            ).exists()
        )
        self.assertTrue(Audit.objects.filter(action="report reviewed").exists())

    def test_shelter_operations_bounds(self):
        sid = self.post(
            self.admin, "shelter", {"name": "Hall", "area": " MIRPUR ", "total": 10}
        ).json()["id"]

        def operate(op, n):
            return self.post(
                self.admin, "shelter", {"id": sid, "operation": op, "quantity": n}
            )

        self.assertEqual(operate("reserve", 6).status_code, 200)
        self.assertEqual(operate("check_in", 5).status_code, 400)
        self.assertEqual(operate("convert", 2).status_code, 200)
        row = Shelter.objects.get(pk=sid)
        self.assertEqual((row.occupied, row.reserved, row.available), (2, 4, 4))
        self.assertEqual(operate("release", 5).status_code, 400)
        self.assertEqual(operate("release", 4).status_code, 200)
        self.assertEqual(operate("check_out", 3).status_code, 400)
        self.assertEqual(operate("check_out", 2).status_code, 200)

    def test_sync_idempotency_and_account_isolation(self):
        data = {
            "kind": "request",
            "item": self.water.pk,
            "quantity": 2,
            "area": "mirpur",
            "client_id": str(uuid.uuid4()),
            "account_id": self.member.pk,
        }
        first = self.post(self.member, "resource", data)
        self.assertEqual(first.status_code, 200)
        second = self.post(self.member, "resource", data)
        self.assertEqual(first.json()["id"], second.json()["id"])
        self.assertFalse(second.json()["saved"])
        self.assertEqual(
            HelpRequest.objects.filter(client_id=data["client_id"]).count(), 1
        )
        self.assertEqual(self.post(self.other, "resource", data).status_code, 403)

    def test_seed_repeatable_preserves_password_and_inventory(self):
        from django.core.management import call_command

        call_command("seed_demo", password="Fictional-Course!47", verbosity=0)
        offer = Offer.objects.get(
            owner__username="demo_donor", item__name="Drinking water"
        )
        offer.quantity = 60
        offer.save()
        count = Offer.objects.count()
        call_command("seed_demo", password="Another-Course!47", verbosity=0)
        self.assertEqual(Offer.objects.count(), count)
        offer.refresh_from_db()
        self.assertEqual(offer.quantity, 60)
        self.assertTrue(
            User.objects.get(username="demo_donor").check_password(
                "Fictional-Course!47"
            )
        )

    def test_constraints_and_private_no_cache(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Shelter.objects.create(name="Bad", area="a", total=1, occupied=2)
        self.client.force_login(self.member)
        response = self.client.get("/api/me/")
        self.assertIn("no-store", response["Cache-Control"])
        self.assertContains(self.client.get("/"), "/static/resilio/theme.js")


class Concurrency(Fixtures, TransactionTestCase):
    def setUp(self):
        self.setup_data()

    def test_simultaneous_allocations_never_over_reserve(self):
        from threading import Barrier

        barrier = Barrier(2)
        clients = [Client(), Client()]
        for client in clients:
            client.force_login(self.vol)

        def reserve_once(index):
            close_old_connections()
            client = clients[index]
            barrier.wait(timeout=10)
            result = client.post(
                "/api/reserve/",
                data=json.dumps(
                    {"offer": self.offer.pk, "request": self.need.pk, "quantity": 15}
                ),
                content_type="application/json",
            )
            close_old_connections()
            return result.status_code

        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(reserve_once, range(2)))
        self.assertEqual(results.count(200), 1, results)
        self.assertTrue(all(r in [200, 400, 409] for r in results), results)
        self.assertEqual(
            Assignment.objects.filter(status="assigned").aggregate(
                n=models.Sum("quantity")
            )["n"],
            15,
        )
        self.assertEqual(self.need.unallocated, 5)


class UpgradedAccess(Fixtures, TestCase):
    def setUp(self):
        self.setup_data()
        self.officer = User.objects.create_user(
            "officer", password="Coursework-Pass!47"
        )
        self.profile = Profile.objects.create(
            user=self.officer,
            role="coordinator",
            organization="Test NGO",
            area="mirpur",
        )

    def test_officer_registration_is_pending_and_never_staff(self):
        r = self.client.post(
            "/register/",
            {
                "username": "new_officer",
                "password1": "Unique-Testing-Pass!87",
                "password2": "Unique-Testing-Pass!87",
                "role": "coordinator",
                "organization": "Relief NGO",
                "approved": "true",
                "is_staff": "true",
            },
        )
        self.assertEqual(r.status_code, 302)
        u = User.objects.get(username="new_officer")
        self.assertFalse(u.is_staff)
        self.assertFalse(u.profile.approved)
        self.assertFalse(self.client.get("/api/me/").json()["user"]["can_coordinate"])

    def test_officer_organization_is_required(self):
        r = self.client.post(
            "/register/",
            {
                "username": "bad_officer",
                "password1": "Unique-Testing-Pass!87",
                "password2": "Unique-Testing-Pass!87",
                "role": "coordinator",
            },
        )
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username="bad_officer").exists())

    def test_admin_approval_and_revocation_enforce_permissions(self):
        data = {
            "offer": self.offer.pk,
            "request": self.need.pk,
            "quantity": 10,
            "volunteer": self.vol.pk,
        }
        self.assertEqual(self.post(self.officer, "reserve", data).status_code, 403)
        self.assertEqual(
            self.post(
                self.vol, "approve", {"id": self.profile.pk, "approved": True}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                self.admin, "approve", {"id": self.profile.pk, "approved": True}
            ).status_code,
            200,
        )
        response = self.post(self.officer, "reserve", data)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            Assignment.objects.get(pk=response.json()["id"]).volunteer, self.vol
        )
        self.assertEqual(
            self.post(
                self.officer,
                "shelter",
                {"name": "Officer Hall", "area": "mirpur", "total": 50},
            ).status_code,
            200,
        )
        self.post(self.admin, "approve", {"id": self.profile.pk, "approved": False})
        self.assertEqual(self.post(self.officer, "reserve", data).status_code, 403)
        self.assertTrue(
            Audit.objects.filter(action="officer approval revoked").exists()
        )

    def test_officer_does_not_gain_admin_moderation_or_receipt_authority(self):
        self.profile.approved = True
        self.profile.save()
        id = self.allocation(10)
        self.move(id, "start")
        self.move(id, "submit", quantity=10)
        self.assertEqual(self.move(id, "confirm", self.officer).status_code, 403)
        self.assertEqual(
            self.post(
                self.officer, "cancel", {"kind": "offer", "id": self.offer.pk}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                self.officer, "approve", {"id": self.profile.pk, "approved": True}
            ).status_code,
            403,
        )

    def test_volunteer_cannot_assign_someone_else(self):
        self.assertEqual(
            self.post(
                self.vol,
                "reserve",
                {
                    "offer": self.offer.pk,
                    "request": self.need.pk,
                    "quantity": 10,
                    "volunteer": self.vol.pk,
                },
            ).status_code,
            403,
        )

    def test_portal_selection_is_checked_not_granted(self):
        response = self.client.post(
            "/accounts/login/?portal=admin",
            {"username": "vol", "password": "Coursework-Pass!47", "portal": "admin"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)
        self.assertEqual(
            self.client.post(
                "/accounts/login/?portal=volunteer",
                {
                    "username": "vol",
                    "password": "Coursework-Pass!47",
                    "portal": "volunteer",
                },
            ).status_code,
            302,
        )

    def test_presence_opt_in_expiry_and_privacy(self):
        self.client.force_login(self.member)
        self.assertEqual(self.client.get("/api/presence/").json()["participants"], [])
        self.assertEqual(Client().get("/api/presence/").status_code, 401)
        self.post(self.vol, "presence", {"enabled": True, "label": "Water Team"})
        self.assertEqual(
            self.client.get("/api/presence/").json()["participants"][0]["label"],
            "Water Team",
        )
        self.assertNotIn("participants", self.client.get("/api/public/").json())
        Profile.objects.filter(user=self.vol).update(
            last_seen=timezone.now() - timedelta(seconds=76)
        )
        self.assertEqual(self.client.get("/api/presence/").json()["participants"], [])

    def test_heartbeat_does_not_reenable_or_edit_another_user(self):
        self.post(self.vol, "presence", {"enabled": True, "label": "Water Team"})
        self.post(self.member, "presence", {"enabled": False, "id": self.vol.pk})
        self.assertTrue(Profile.objects.get(user=self.vol).share_presence)
        self.post(self.vol, "presence", {"enabled": False})
        self.post(self.vol, "presence", {})
        self.assertFalse(Profile.objects.get(user=self.vol).share_presence)
        self.assertIsNone(Profile.objects.get(user=self.vol).last_seen)

    def test_logout_clears_presence_and_account_pages_render(self):
        self.post(self.vol, "presence", {"enabled": True})
        self.client.force_login(self.vol)
        self.client.post("/accounts/logout/")
        self.assertIsNone(Profile.objects.get(user=self.vol).last_seen)
        self.assertContains(self.client.get("/access/"), "NGO / Relief Officer")
        self.assertContains(
            self.client.get("/accounts/login/?portal=admin"), "Workspace"
        )


class CloudDeploymentTests(TestCase):
    def test_catalog_contains_no_demo_users_and_is_repeatable(self):
        from django.core.management import call_command

        call_command("initialize_catalog", verbosity=0)
        call_command("initialize_catalog", verbosity=0)
        self.assertEqual(Item.objects.count(), 8)
        self.assertEqual(User.objects.count(), 0)

    def test_private_admin_bootstrap_is_repeatable_without_reset(self):
        from django.core.management import call_command
        from unittest.mock import patch

        with patch.dict(
            "os.environ",
            {
                "RESILIO_ADMIN_USERNAME": "cloud_owner",
                "RESILIO_ADMIN_PASSWORD": "Unique-Cloud-Owner!94",
                "RESILIO_ADMIN_EMAIL": "cloud@example.com",
            },
        ):
            call_command("bootstrap_cloud_admin", verbosity=0)
        user = User.objects.get(username="cloud_owner")
        self.assertTrue(user.is_superuser)
        self.assertTrue(user.check_password("Unique-Cloud-Owner!94"))
        with patch.dict(
            "os.environ",
            {
                "RESILIO_ADMIN_USERNAME": "cloud_owner",
                "RESILIO_ADMIN_PASSWORD": "Another-Cloud-Pass!45",
            },
        ):
            call_command("bootstrap_cloud_admin", verbosity=0)
        user.refresh_from_db()
        self.assertTrue(user.check_password("Unique-Cloud-Owner!94"))

    def test_bootstrap_refuses_to_promote_an_existing_public_account(self):
        from django.core.management import call_command, CommandError
        from unittest.mock import patch

        user = User.objects.create_user("claimed", password="Original-User-Pass!47")
        with patch.dict(
            "os.environ",
            {
                "RESILIO_ADMIN_USERNAME": "claimed",
                "RESILIO_ADMIN_PASSWORD": "Unique-Cloud-Owner!94",
            },
        ):
            with self.assertRaises(CommandError):
                call_command("bootstrap_cloud_admin", verbosity=0)
        user.refresh_from_db()
        self.assertFalse(user.is_staff)

    def test_bootstrap_rejects_partial_configuration_and_short_password(self):
        from django.core.management import call_command, CommandError
        from unittest.mock import patch

        with patch.dict(
            "os.environ",
            {"RESILIO_ADMIN_USERNAME": "newowner", "RESILIO_ADMIN_PASSWORD": ""},
        ):
            with self.assertRaises(CommandError):
                call_command("bootstrap_cloud_admin", verbosity=0)
        with patch.dict(
            "os.environ",
            {"RESILIO_ADMIN_USERNAME": "newowner", "RESILIO_ADMIN_PASSWORD": "short"},
        ):
            with self.assertRaises(CommandError):
                call_command("bootstrap_cloud_admin", verbosity=0)
        self.assertFalse(User.objects.filter(username="newowner").exists())
