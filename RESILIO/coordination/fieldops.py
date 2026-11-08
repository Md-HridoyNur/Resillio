"""Field coordination additions; writes run under the API's transaction/mutex."""

import json
from functools import lru_cache
from pathlib import Path
from uuid import UUID
from datetime import timedelta
from decimal import Decimal, InvalidOperation
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from django.contrib.auth import get_user_model
from .models import *
from . import services as s


@lru_cache(maxsize=1)
def directory():
    return json.loads(
        (Path(__file__).parent / "data/local_areas_2026.json").read_text(
            encoding="utf-8"
        )
    )


def locality(data, district_id):
    code = s.text(data, "upazila", 20, False)
    if code and not any(
        x["code"] == code and x["district"] == district_id
        for x in directory()["upazilas"]
    ):
        s.fail("Choose an upazila in the selected district.", "upazila")
    return code


def apply_place(obj, data):
    if "upazila" in data:
        obj.upazila = locality(data, obj.district_id)
    elif obj.upazila and not any(
        x["code"] == obj.upazila and x["district"] == obj.district_id
        for x in directory()["upazilas"]
    ):
        obj.upazila = ""
    if "latitude" not in data and "longitude" not in data:
        return
    lat, lon = data.get("latitude"), data.get("longitude")
    if lat in ["", None] and lon in ["", None]:
        obj.latitude = obj.longitude = None
        obj.pin_label = ""
        return
    s.require(
        data.get("pin_consent") == "yes",
        "Confirm who can see this saved pin before submitting.",
    )
    try:
        lat, lon = Decimal(str(lat)), Decimal(str(lon))
        if (
            not lat.is_finite()
            or not lon.is_finite()
            or not -90 <= lat <= 90
            or not -180 <= lon <= 180
        ):
            raise ValueError()
    except (ValueError, TypeError, InvalidOperation):
        s.fail(
            "Enter both finite latitude and longitude within valid bounds.", "latitude"
        )
    obj.latitude = lat.quantize(Decimal(".000001"))
    obj.longitude = lon.quantize(Decimal(".000001"))
    obj.pin_label = s.text(data, "pin_label", 160, False)


def pin(obj):
    return (
        None
        if obj.latitude is None or obj.longitude is None
        else {
            "latitude": str(obj.latitude),
            "longitude": str(obj.longitude),
            "label": obj.pin_label,
            "source": "creator-provided",
        }
    )


def assignment_access(user, assignment):
    s.require(
        s.coordinator(user)
        or user.pk
        in [
            assignment.volunteer_id,
            assignment.offer.owner_id,
            assignment.request.owner_id,
        ]
    )


def messages(user, assignment_id, before=None):
    assignment = Assignment.objects.select_related("offer", "request").get(
        pk=assignment_id
    )
    assignment_access(user, assignment)
    query = assignment.messages.select_related("sender").order_by("-id")
    if before:
        query = query.filter(pk__lt=int(before))
    rows = list(query[:100])
    return {
        "messages": [
            {
                "id": x.pk,
                "body": x.body,
                "sender": x.sender.username,
                "created_at": x.created_at.isoformat(),
            }
            for x in reversed(rows)
        ],
        "has_more": len(rows) == 100,
        "before": rows[-1].pk if rows else None,
    }


def send_message(user, data):
    assignment = Assignment.objects.select_related("offer", "request").get(
        pk=data.get("assignment")
    )
    assignment_access(user, assignment)
    cid = UUID(str(data.get("client_id")))
    existing = AssignmentMessage.objects.filter(
        assignment=assignment, sender=user, client_id=cid
    ).first()
    if existing:
        return existing
    obj = AssignmentMessage.objects.create(
        assignment=assignment,
        sender=user,
        client_id=cid,
        body=s.text(data, "body", 1500),
    )
    s.notify(
        set(
            [
                assignment.volunteer_id,
                assignment.offer.owner_id,
                assignment.request.owner_id,
            ]
        )
        - {user.pk},
        f"New message in assignment #{assignment.pk}.",
    )
    return obj


def emergencies(user):
    query = EmergencyCase.objects.select_related(
        "owner", "district__division", "assigned_to"
    ).order_by("-created_at")
    return (
        query
        if s.coordinator(user)
        else query.filter(Q(owner=user) | Q(assigned_to=user))
    )


def emergency_data(obj):
    return {
        "id": obj.pk,
        "kind": obj.kind,
        "people": obj.people,
        "description": obj.description,
        "contact": obj.contact,
        "area": obj.area,
        "district": obj.district_id,
        "division": obj.district.division_id,
        "upazila": obj.upazila,
        "owner": obj.owner.username,
        "owner_id": obj.owner_id,
        "assigned_to": obj.assigned_to_id,
        "assigned_name": obj.assigned_to.username if obj.assigned_to_id else None,
        "status": obj.status,
        "pin": pin(obj),
        "created_at": obj.created_at.isoformat(),
        "updated_at": obj.updated_at.isoformat(),
    }


def emergency(user, data):
    if not data.get("id"):
        cid = UUID(str(data.get("client_id")))
        obj = EmergencyCase.objects.filter(owner=user, client_id=cid).first()
        if obj:
            return obj
        district = s.validated_district(data)
        if not district:
            s.fail("Select a district.", "district")
        kind = data.get("kind")
        if kind not in ["medical", "trapped", "evacuation", "flood", "other"]:
            s.fail("Choose an emergency type.")
        people = s.quantity(data.get("people"), "people", True)
        if people > 10000:
            s.fail("Enter at most 10000 people.")
        obj = EmergencyCase(
            owner=user,
            client_id=cid,
            district=district,
            kind=kind,
            people=people,
            area=s.area(s.text(data, "area", 100)),
            description=s.text(data, "description", 2000),
            contact=s.text(data, "contact", 80, False),
        )
        apply_place(obj, data)
        obj.full_clean()
        obj.save()
        users = (
            get_user_model()
            .objects.filter(
                Q(is_staff=True)
                | Q(profile__role="coordinator", profile__approved=True),
                is_active=True,
            )
            .values_list("pk", flat=True)
            .distinct()
        )
        s.notify(
            users,
            f"Emergency case #{obj.pk} received in {district.name}. Review the emergency desk.",
        )
        s.audit(user, "emergency received", obj)
        return obj
    obj = EmergencyCase.objects.select_related("owner", "assigned_to").get(
        pk=data["id"]
    )
    action = data.get("transition")
    if action == "cancel":
        s.require(user.pk == obj.owner_id or s.coordinator(user))
        if obj.status in ["resolved", "cancelled"]:
            s.fail("This case is already closed.")
        obj.status = "cancelled"
    else:
        s.require(s.coordinator(user))
        if action == "acknowledge" and obj.status == "received":
            obj.status = "acknowledged"
        elif action == "assign" and obj.status == "acknowledged":
            volunteer = get_user_model().objects.get(
                pk=data.get("volunteer"), is_active=True, profile__role="volunteer"
            )
            obj.assigned_to = volunteer
            obj.status = "assigned"
        elif action == "resolve" and obj.status == "assigned":
            obj.status = "resolved"
        else:
            s.fail("Invalid emergency status transition. Refresh the case.")
    obj.save()
    s.audit(user, "emergency " + obj.status, obj)
    recipients = [obj.owner_id] + ([obj.assigned_to_id] if obj.assigned_to_id else [])
    s.notify(recipients, f"Emergency case #{obj.pk}: {obj.status}.")
    return obj


def announcement(user, data):
    s.require(s.coordinator(user))
    if data.get("id"):
        obj = Announcement.objects.get(pk=data["id"])
        s.require(user.is_staff or obj.author_id == user.pk)
        obj.active = False
        obj.save(update_fields=["active"])
        s.audit(user, "announcement withdrawn", obj)
        return obj
    expires = parse_datetime(str(data.get("expires_at", "")))
    if (
        not expires
        or timezone.is_naive(expires)
        or not timezone.now() < expires <= timezone.now() + timedelta(days=7)
    ):
        s.fail("Choose an expiry within the next seven days.")
    obj = Announcement.objects.create(
        author=user,
        district=s.validated_district(data),
        title=s.text(data, "title", 160),
        body=s.text(data, "body", 3000),
        expires_at=expires,
    )
    s.audit(user, "announcement published", obj)
    return obj


def announcement_data(obj):
    profile = getattr(obj.author, "profile", None)
    return {
        "id": obj.pk,
        "title": obj.title,
        "body": obj.body,
        "district": obj.district_id,
        "author": (
            profile.organization
            if profile and profile.organization
            else "RESILIO coordination desk"
        ),
        "active": obj.active,
        "created_at": obj.created_at.isoformat(),
        "expires_at": obj.expires_at.isoformat(),
        "issuer": (
            "RESILIO administrator"
            if obj.author.is_staff
            else "Approved RESILIO officer"
        ),
    }


def reconfirm(user, data):
    model = (
        Offer
        if data.get("kind") == "offer"
        else HelpRequest if data.get("kind") == "request" else None
    )
    if not model:
        s.fail("Choose an offer or request.")
    obj = model.objects.get(pk=data.get("id"))
    s.owned(user, obj)
    if obj.status != "open":
        s.fail("Only open records can be reconfirmed.")
    obj.confirmed_at = timezone.now()
    obj.save(update_fields=["confirmed_at"])
    s.audit(user, "need or supply reconfirmed", obj)
    return obj


def shelter_place(user, data):
    s.require(s.coordinator(user))
    obj = Shelter.objects.get(pk=data.get("id"))
    if "district" in data:
        obj.district = s.validated_district(data)
    obj.area = s.area(s.text(data, "area", 100))
    apply_place(obj, data)
    obj.full_clean()
    obj.save()
    s.audit(user, "shelter location updated", obj)
    return obj


def private_extensions(user):
    requests = (
        HelpRequest.objects.all()
        if s.coordinator(user)
        else HelpRequest.objects.filter(
            Q(owner=user)
            | Q(
                assignments__volunteer=user,
                assignments__status__in=ACTIVE + ["delivered"],
            )
        ).distinct()
    )
    return {
        "request_pins": {str(x.pk): pin(x) for x in requests if x.latitude is not None},
        "emergencies": [emergency_data(x) for x in emergencies(user)[:200]],
        "announcements_authored": [
            announcement_data(x)
            for x in Announcement.objects.filter(author=user).order_by("-created_at")[
                :100
            ]
        ],
    }
