from datetime import timedelta
from decimal import Decimal
from uuid import uuid4
from django.test import TestCase, Client
from django.utils import timezone
from django.db import IntegrityError, transaction
from .tests import Fixtures
from .models import *
from . import fieldops as f


class FieldOperations(Fixtures, TestCase):
    def setUp(self):
        self.setup_data()
        self.dhaka = District.objects.get(pk="dhaka")
        self.local = next(
            x["code"] for x in f.directory()["upazilas"] if x["district"] == "dhaka"
        )

    def me(self, user):
        client = Client()
        client.force_login(user)
        return client.get("/api/me/").json()

    def get(self, user, path):
        client = Client()
        client.force_login(user)
        return client.get(path)

    def request_data(self, **extra):
        return {
            "kind": "request",
            "item": self.water.pk,
            "quantity": 5,
            "area": "Local ward",
            "district": "dhaka",
            "upazila": self.local,
            "latitude": 23.8103,
            "longitude": 90.4125,
            "pin_consent": "yes",
            "pin_label": "Private home",
            **extra,
        }

    def case_data(self, **extra):
        return {
            "kind": "evacuation",
            "district": "dhaka",
            "upazila": self.local,
            "area": "Local ward",
            "people": 3,
            "description": "Evacuation assistance needed",
            "contact": "Private contact",
            "client_id": str(uuid4()),
            "latitude": 23.8103,
            "longitude": 90.4125,
            "pin_consent": "yes",
            **extra,
        }

    def test_private_request_pins_and_authorized_assignment(self):
        response = self.post(self.member, "resource", self.request_data())
        self.assertEqual(response.status_code, 200, response.content)
        pk = response.json()["id"]
        key = str(pk)
        public = self.client.get("/api/public/").json()
        row = next(x for x in public["requests"] if x["id"] == pk)
        self.assertIsNone(row["pin"])
        self.assertNotIn("Private home", str(public))
        self.assertEqual(row["upazila"], self.local)
        self.assertIn(key, self.me(self.member)["request_pins"])
        self.assertIn(key, self.me(self.admin)["request_pins"])
        self.assertNotIn(key, self.me(self.other)["request_pins"])
        assignment = self.post(
            self.vol, "reserve", {"offer": self.offer.pk, "request": pk, "quantity": 5}
        ).json()["id"]
        self.assertIn(key, self.me(self.vol)["request_pins"])
        self.assertNotIn(key, self.me(self.donor)["request_pins"])
        self.post(self.vol, "transition", {"id": assignment, "transition": "cancel"})
        self.assertNotIn(key, self.me(self.vol)["request_pins"])

    def test_explicit_pin_consent_bounds_and_locality_parent(self):
        self.assertEqual(len(f.directory()["district_bn"]), 64)
        for extra, status in [
            ({"pin_consent": ""}, 403),
            ({"latitude": 91}, 400),
            ({"longitude": ""}, 400),
            ({"latitude": "NaN"}, 400),
            ({"upazila": "not-real"}, 400),
            ({"district": "sylhet"}, 400),
        ]:
            self.assertEqual(
                self.post(
                    self.member, "resource", self.request_data(**extra)
                ).status_code,
                status,
                extra,
            )
        response = self.post(self.donor, "resource", self.request_data(kind="offer"))
        self.assertEqual(response.status_code, 200, response.content)
        row = next(
            x
            for x in self.client.get("/api/public/").json()["offers"]
            if x["id"] == response.json()["id"]
        )
        self.assertEqual(float(row["pin"]["latitude"]), 23.8103)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Offer.objects.create(
                owner=self.donor, item=self.water, quantity=2, area="x", latitude=23
            )

    def test_shelter_pin_update_preserves_capacity(self):
        obj = Shelter.objects.create(
            name="Facility", area="local ward", total=100, occupied=15, reserved=5
        )
        data = {"id": obj.pk, **self.request_data()}
        self.assertEqual(self.post(self.member, "shelter_place", data).status_code, 403)
        self.assertEqual(self.post(self.admin, "shelter_place", data).status_code, 200)
        obj.refresh_from_db()
        self.assertEqual((obj.total, obj.occupied, obj.reserved), (100, 15, 5))
        self.assertIsNotNone(
            self.client.get("/api/public/").json()["shelters"][0]["pin"]
        )
        data.update(latitude="", longitude="", pin_consent="")
        self.assertEqual(self.post(self.admin, "shelter_place", data).status_code, 200)
        obj.refresh_from_db()
        self.assertIsNone(obj.latitude)

    def test_emergency_workflow_privacy_and_duplicate_retry(self):
        data = self.case_data()
        response = self.post(self.member, "emergency", data)
        self.assertEqual(response.status_code, 200, response.content)
        pk = response.json()["id"]
        self.assertEqual(self.post(self.member, "emergency", data).json()["id"], pk)
        self.assertEqual(EmergencyCase.objects.count(), 1)
        self.assertEqual(len(self.me(self.other)["emergencies"]), 0)
        self.assertEqual(len(self.me(self.member)["emergencies"]), 1)
        self.assertNotIn(
            "Private contact", self.client.get("/api/public/").content.decode()
        )
        self.assertEqual(
            self.post(
                self.member, "emergency", {"id": pk, "transition": "acknowledge"}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                self.admin, "emergency", {"id": pk, "transition": "resolve"}
            ).status_code,
            400,
        )
        self.assertEqual(
            self.post(
                self.admin, "emergency", {"id": pk, "transition": "acknowledge"}
            ).status_code,
            200,
        )
        self.assertEqual(
            self.post(
                self.admin,
                "emergency",
                {"id": pk, "transition": "assign", "volunteer": self.other.pk},
            ).status_code,
            404,
        )
        self.assertEqual(
            self.post(
                self.admin,
                "emergency",
                {"id": pk, "transition": "assign", "volunteer": self.vol.pk},
            ).status_code,
            200,
        )
        self.assertEqual(len(self.me(self.vol)["emergencies"]), 1)
        self.assertEqual(
            self.post(
                self.admin, "emergency", {"id": pk, "transition": "resolve"}
            ).status_code,
            200,
        )
        self.assertEqual(EmergencyCase.objects.get(pk=pk).status, "resolved")

    def test_emergency_requires_server_validation(self):
        for extra in [
            {"people": 0},
            {"people": 10001},
            {"district": ""},
            {"kind": "fake"},
            {"description": ""},
            {"client_id": "wrong"},
        ]:
            self.assertEqual(
                self.post(
                    self.member, "emergency", self.case_data(**extra)
                ).status_code,
                400,
                extra,
            )

    def test_announcements_permissions_expiry_withdrawal_and_revocation(self):
        officer = Profile.objects.create(
            user=self.other,
            role="coordinator",
            approved=False,
            organization="Example NGO",
        )
        data = {
            "title": "Distribution",
            "body": "Water distribution at the relief center.",
            "district": "dhaka",
            "expires_at": (timezone.now() + timedelta(hours=2)).isoformat(),
        }
        self.assertEqual(self.post(self.other, "announcement", data).status_code, 403)
        officer.approved = True
        officer.save()
        response = self.post(self.other, "announcement", data)
        self.assertEqual(response.status_code, 200, response.content)
        pk = response.json()["id"]
        self.assertEqual(
            len(self.client.get("/api/public/").json()["announcements"]), 1
        )
        officer.approved = False
        officer.save()
        self.assertEqual(
            len(self.client.get("/api/public/").json()["announcements"]), 0
        )
        officer.approved = True
        officer.save()
        for delta in [timedelta(hours=-1), timedelta(days=8)]:
            self.assertEqual(
                self.post(
                    self.other,
                    "announcement",
                    {**data, "expires_at": (timezone.now() + delta).isoformat()},
                ).status_code,
                400,
            )
        self.assertEqual(
            self.post(self.admin, "announcement", {"id": pk}).status_code, 200
        )
        self.assertEqual(self.client.get("/api/public/").json()["announcements"], [])

    def test_assignment_messages_participants_only_and_idempotent(self):
        pk = self.allocation(5)
        data = {
            "assignment": pk,
            "body": "Meet at the collection point.",
            "client_id": str(uuid4()),
        }
        self.assertEqual(self.post(self.other, "message", data).status_code, 403)
        response = self.post(self.member, "message", data)
        self.assertEqual(response.status_code, 200, response.content)
        self.assertEqual(
            self.post(self.member, "message", data).json()["id"], response.json()["id"]
        )
        self.assertEqual(AssignmentMessage.objects.count(), 1)
        for user in [self.member, self.donor, self.vol, self.admin]:
            r = self.get(user, f"/api/messages/?assignment={pk}")
            self.assertEqual(r.status_code, 200)
            self.assertIn("no-store", r["Cache-Control"])
            self.assertEqual(len(r.json()["messages"]), 1)
        self.assertEqual(
            self.get(self.other, f"/api/messages/?assignment={pk}").status_code, 403
        )
        self.assertEqual(
            self.client.get(f"/api/messages/?assignment={pk}").status_code, 401
        )
        self.assertEqual(
            self.post(
                self.member,
                "message",
                {**data, "client_id": str(uuid4()), "body": "x" * 1501},
            ).status_code,
            400,
        )

    def test_reconfirmation_does_not_change_stock_or_assignments(self):
        pk = self.allocation(5)
        before = self.offer.available
        self.assertEqual(
            self.post(
                self.other, "reconfirm", {"kind": "offer", "id": self.offer.pk}
            ).status_code,
            403,
        )
        self.assertEqual(
            self.post(
                self.donor, "reconfirm", {"kind": "offer", "id": self.offer.pk}
            ).status_code,
            200,
        )
        self.offer.refresh_from_db()
        self.assertEqual(self.offer.available, before)
        self.assertEqual(Assignment.objects.count(), 1)
        Offer.objects.filter(pk=self.offer.pk).update(
            confirmed_at=timezone.now() - timedelta(hours=25)
        )
        row = next(
            x
            for x in self.client.get("/api/public/").json()["offers"]
            if x["id"] == self.offer.pk
        )
        self.assertFalse(row["fresh"])

    def test_public_catalog_under_windows_style_default_encoding(self):
        from pathlib import Path
        from unittest.mock import patch

        original_read = Path.read_text

        def windows_read(path, *args, **kwargs):
            kwargs.setdefault("encoding", "cp1252")
            return original_read(path, *args, **kwargs)

        f.directory.cache_clear()
        try:
            with patch.object(Path, "read_text", windows_read):
                response = self.client.get("/api/public/")
                self.assertEqual(response.status_code, 200, response.content)
                self.assertEqual(len(response.json()["items"]), 8)
                self.assertEqual(len(response.json()["geography"]["upazilas"]), 494)
                self.assertEqual(
                    response.json()["geography"]["district_bn"]["dhaka"], "ঢাকা"
                )
        finally:
            f.directory.cache_clear()
