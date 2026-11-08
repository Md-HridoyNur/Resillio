"""Operational writes require an atomic transaction and acquire_write_lock()."""

from decimal import Decimal, InvalidOperation
from uuid import UUID
from django.core.exceptions import ValidationError, PermissionDenied
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from .models import *


def require(ok, message="You do not have permission for this action."):
    if not ok:
        raise PermissionDenied(message)


def fail(message, field=None):
    raise ValidationError({field: message} if field else message)


def text(data, key, maxlen=2000, required=True):
    value = str(data.get(key, "")).strip()
    if (required and not value) or len(value) > maxlen:
        fail(f"Enter {key} (maximum {maxlen} characters).", key)
    return value


def quantity(value, field="quantity", integer=False):
    try:
        n = Decimal(str(value))
        if (
            not n.is_finite()
            or n <= 0
            or n > 99999999
            or n.as_tuple().exponent < -2
            or (integer and n != int(n))
        ):
            raise ValueError()
        return int(n) if integer else n
    except (ValueError, InvalidOperation, TypeError):
        fail(
            "Enter a positive quantity, up to 99,999,999, with at most two decimals.",
            field,
        )


def area(value):
    return " ".join(str(value).strip().lower().split())


def audit(user, action, obj, detail=""):
    Audit.objects.create(
        actor=user,
        action=action,
        target=f"{obj.__class__.__name__} #{obj.pk}",
        detail=detail,
    )


def notify(users, message):
    for uid in set(users):
        Notification.objects.create(user_id=uid, text=message)


def coordinator(user):
    return (
        user.is_staff
        or Profile.objects.filter(user=user, role="coordinator", approved=True).exists()
    )


def volunteer(user):
    return (
        coordinator(user)
        or Profile.objects.filter(user=user, role="volunteer").exists()
    )


def owned(user, obj):
    require(user.is_staff or obj.owner_id == user.id)


def resource(user, data):
    kind = data.get("kind")
    if kind not in ["offer", "request"]:
        fail("Choose offer or request.", "kind")
    model = Offer if kind == "offer" else HelpRequest
    obj = model.objects.get(pk=data["id"]) if data.get("id") else None
    if obj:
        owned(user, obj)
    cid = None
    if data.get("client_id"):
        if kind != "request":
            fail("Client identifiers apply to help requests only.")
        try:
            cid = UUID(str(data["client_id"]))
        except (ValueError, TypeError):
            fail("Invalid client identifier.", "client_id")
        require(
            int(data.get("account_id", -1)) == user.pk,
            "Sign in as the account that created this local request.",
        )
        existing = HelpRequest.objects.filter(owner=user, client_id=cid).first()
        if existing:
            return existing, False
    if obj:
        if obj.status != "open":
            fail("Only open records can be edited.")
        if obj.assignments.exclude(status="cancelled").exists():
            fail(
                "This record has allocations or delivery history; create a new record instead."
            )
    item = Item.objects.get(pk=data.get("item"))
    qty = quantity(data.get("quantity"))
    loc = area(text(data, "area", 100))
    desc = text(data, "description", 2000, False)
    if not obj:
        obj = model(owner=user)
    obj.item = item
    obj.quantity = qty
    obj.area = loc
    obj.description = desc
    if "district" in data:
        obj.district = validated_district(data)
    if kind == "offer":
        expiry = data.get("expires_at")
        date = parse_datetime(expiry) if expiry else None
        if expiry and date is None:
            fail("Enter a valid expiry date.", "expires_at")
        if date and timezone.is_naive(date):
            date = timezone.make_aware(date)
        if date and date <= timezone.now():
            fail("Expiry must be in the future.", "expires_at")
        obj.expires_at = date
    else:
        urgency = data.get("urgency", "normal")
        if urgency not in ["normal", "urgent", "critical"]:
            fail("Invalid urgency.", "urgency")
        obj.urgency = urgency
        if cid:
            obj.client_id = cid
    from .fieldops import apply_place

    apply_place(obj, data)
    obj.confirmed_at = timezone.now()
    obj.full_clean()
    obj.save()
    audit(user, "resource saved", obj)
    return obj, True


def cancel_resource(user, data):
    if data.get("kind") not in ["offer", "request"]:
        fail("Choose offer or request.", "kind")
    model = Offer if data.get("kind") == "offer" else HelpRequest
    obj = model.objects.get(pk=data.get("id"))
    owned(user, obj)
    if obj.status != "open":
        fail("Only open records can be cancelled.")
    if obj.assignments.filter(status__in=ACTIVE).exists():
        fail(
            "Cancel active assignments first. Awaiting receipts must be resolved before cancellation."
        )
    obj.status = "cancelled"
    obj.save()
    audit(user, "resource cancelled", obj)
    notify([obj.owner_id], f"{obj.__class__.__name__} #{obj.pk} was cancelled.")


def reserve(user, data):
    require(
        volunteer(user), "A volunteer account is required to coordinate deliveries."
    )
    offer = Offer.objects.get(pk=data.get("offer"))
    req = HelpRequest.objects.get(pk=data.get("request"))
    n = quantity(data.get("quantity"))
    if offer.item_id != req.item_id:
        fail("Items and canonical units must match.")
    if req.status != "open" or offer.status != "open":
        fail("Both records must be open.")
    if n > offer.available:
        fail("Insufficient available supply. Refresh the recommendations.")
    if n > req.unallocated:
        fail("This request no longer has enough unallocated need.")
    assignee = user
    if data.get("volunteer"):
        require(
            coordinator(user),
            "Only an approved officer or administrator can assign another volunteer.",
        )
        from django.contrib.auth import get_user_model

        assignee = get_user_model().objects.get(pk=data["volunteer"], is_active=True)
        require(
            Profile.objects.filter(user=assignee, role="volunteer").exists(),
            "Select a volunteer account.",
        )
    obj = Assignment.objects.create(
        offer=offer, request=req, volunteer=assignee, quantity=n
    )
    audit(user, "assignment reserved", obj, str(n))
    notify(
        [offer.owner_id, req.owner_id, assignee.pk, user.pk],
        f"Assignment #{obj.pk}: {n} {offer.item.unit} reserved for request #{req.pk}.",
    )
    return obj


def transition(user, data):
    obj = Assignment.objects.select_related("request", "offer__item").get(
        pk=data.get("id")
    )
    action = data.get("transition")
    if action == "confirm":
        require(
            user.is_staff or obj.request.owner_id == user.id,
            "Only the requester or an administrator may confirm receipt.",
        )
        if obj.status != "awaiting_confirmation":
            fail("Receipt is not awaiting confirmation or was already confirmed.")
        Delivery.objects.create(
            assignment=obj, quantity=obj.delivered_quantity, confirmed_by=user
        )
        obj.status = "delivered"
        obj.save()
        req = obj.request
        if req.delivered >= req.quantity:
            req.status = "fulfilled"
            req.save()
    else:
        require(coordinator(user) or obj.volunteer_id == user.id)
        if action == "start" and obj.status == "assigned":
            obj.status = "in_progress"
        elif action == "submit" and obj.status == "in_progress":
            n = quantity(data.get("quantity"))
            if n > obj.quantity:
                fail("Delivered quantity cannot exceed the reservation.", "quantity")
            obj.delivered_quantity = n
            obj.status = "awaiting_confirmation"
        elif action == "cancel" and obj.status in ["assigned", "in_progress"]:
            obj.status = "cancelled"
        else:
            fail(
                "Invalid transition. Awaiting receipts cannot be cancelled; an administrator can resolve them."
            )
        obj.save()
    audit(user, f"assignment {action}", obj, str(obj.delivered_quantity))
    notify(
        [obj.request.owner_id, obj.offer.owner_id, obj.volunteer_id],
        f"Assignment #{obj.pk}: {obj.get_status_display()}.",
    )
    return obj


def shelter(user, data):
    require(coordinator(user))
    if not data.get("id"):
        obj = Shelter(
            district=validated_district(data) if "district" in data else None,
            name=text(data, "name", 120),
            area=area(text(data, "area", 100)),
            total=quantity(data.get("total"), "total", True),
            description=text(data, "description", 2000, False),
        )
    else:
        obj = Shelter.objects.get(pk=data["id"])
        n = quantity(data.get("quantity"), integer=True)
        action = data.get("operation")
        if action == "check_in":
            obj.occupied += n
        elif action == "check_out":
            obj.occupied -= n
        elif action == "reserve":
            obj.reserved += n
        elif action == "release":
            obj.reserved -= n
        elif action == "convert":
            obj.reserved -= n
            obj.occupied += n
        else:
            fail("Unknown shelter operation.")
        if (
            min(obj.occupied, obj.reserved) < 0
            or obj.occupied + obj.reserved > obj.total
        ):
            fail("Shelter operation exceeds capacity or available guests/reservations.")
    if not data.get("id"):
        from .fieldops import apply_place

        apply_place(obj, data)
    obj.full_clean()
    obj.save()
    audit(
        user,
        "shelter updated",
        obj,
        f"{obj.occupied} occupied, {obj.reserved} reserved / {obj.total}",
    )
    return obj


def report(user, data):
    if data.get("kind") not in ["offer", "request"]:
        fail("Choose offer or request.", "kind")
    model = Offer if data.get("kind") == "offer" else HelpRequest
    obj = model.objects.get(pk=data.get("id"))
    values = {"offer": obj} if model == Offer else {"request": obj}
    record = Report.objects.create(
        reporter=user, reason=text(data, "reason", 500), **values
    )
    audit(user, "report created", record)
    return record


def review(user, data):
    require(user.is_staff)
    obj = Report.objects.get(pk=data.get("id"))
    if obj.reviewed_at:
        fail("This report is already reviewed.")
    obj.decision = text(data, "decision", 500)
    obj.reviewed_by = user
    obj.reviewed_at = timezone.now()
    obj.save()
    audit(user, "report reviewed", obj, obj.decision)
    notify([obj.reporter_id], f"Report #{obj.pk} reviewed: {obj.decision}")
    return obj


def approve_officer(user, data):
    require(user.is_staff)
    obj = Profile.objects.select_related("user").get(
        pk=data.get("id"), role="coordinator"
    )
    approved = data.get("approved")
    if type(approved) is not bool:
        fail("Choose approve or revoke.")
    obj.approved = approved
    obj.save(update_fields=["approved"])
    audit(
        user,
        "officer approved" if approved else "officer approval revoked",
        obj,
        obj.organization,
    )
    notify(
        [obj.user_id],
        "Your NGO / relief officer access was "
        + ("approved." if approved else "revoked."),
    )


def acquire_write_lock():
    """Equivalent serialization on both supported databases, acquired BEFORE reads.
    SQLite: BEGIN IMMEDIATE already reserves the writer. PostgreSQL: lock the
    migration-created singleton row until COMMIT. This intentionally serializes
    operational writes for a modest course deployment, including pending receipt
    checks, multiple offers/requests, stock edits, shelters and sync retries.
    """
    from django.db import connection

    if not connection.in_atomic_block:
        raise RuntimeError("Operational writes require transaction.atomic().")
    if connection.vendor == "postgresql":
        with connection.cursor() as cursor:
            cursor.execute("SET LOCAL lock_timeout = '8s'")
        CoordinationLock.objects.select_for_update().get(pk=1)


def validated_district(data):
    if not data.get("district"):
        return None
    obj = District.objects.get(pk=data["district"])
    if data.get("division") and obj.division_id != data["division"]:
        fail("Choose a district in the selected division.", "district")
    return obj


def clear_location(profile):
    profile.share_location = False
    profile.latitude = None
    profile.longitude = None
    profile.location_accuracy = None
    profile.location_updated_at = None


def location_update(user, data):
    from datetime import timedelta
    import math

    obj, _ = Profile.objects.get_or_create(user=user)
    if type(data.get("enabled")) is not bool:
        fail("Choose whether to share the pin.")
    if not data["enabled"]:
        clear_location(obj)
        obj.save(
            update_fields=[
                "share_location",
                "latitude",
                "longitude",
                "location_accuracy",
                "location_updated_at",
            ]
        )
        audit(user, "location sharing disabled", obj)
        return
    require(obj.share_presence, "Enable presence sharing before sharing a precise pin.")
    try:
        lat = Decimal(str(data.get("latitude")))
        lon = Decimal(str(data.get("longitude")))
        accuracy = float(data.get("accuracy"))
        if (
            not lat.is_finite()
            or not lon.is_finite()
            or not -90 <= lat <= 90
            or not -180 <= lon <= 180
            or not math.isfinite(accuracy)
            or not 0 <= accuracy <= 100000
        ):
            raise ValueError()
    except (ValueError, TypeError, InvalidOperation):
        fail("Location requires finite latitude, longitude and accuracy values.")
    captured = parse_datetime(str(data.get("captured_at", "")))
    if (
        not captured
        or timezone.is_naive(captured)
        or captured < timezone.now() - timedelta(minutes=2)
        or captured > timezone.now() + timedelta(seconds=30)
    ):
        fail("Location reading is old or invalid. Capture a fresh location first.")
    first = not obj.share_location
    obj.share_location = True
    obj.last_seen = timezone.now()
    obj.latitude = lat.quantize(Decimal(".000001"))
    obj.longitude = lon.quantize(Decimal(".000001"))
    obj.location_accuracy = accuracy
    obj.location_updated_at = captured
    obj.save(
        update_fields=[
            "share_location",
            "latitude",
            "longitude",
            "location_accuracy",
            "location_updated_at",
            "last_seen",
        ]
    )
    if first:
        audit(
            user,
            "location sharing enabled",
            obj,
            "Shared with signed-in participants; no coordinate history is recorded.",
        )
