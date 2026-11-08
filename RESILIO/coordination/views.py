import json
from pathlib import Path
from django.conf import settings
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError, PermissionDenied, ObjectDoesNotExist
from django.db import transaction, OperationalError, IntegrityError
from django.db.models import Q
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.views.decorators.csrf import ensure_csrf_cookie
from django.views.decorators.cache import never_cache
from django.utils import timezone
from .models import *
from .forms import RegistrationForm
from datetime import timedelta
from . import services as s
from . import fieldops as f


@ensure_csrf_cookie
@never_cache
def home(request):
    return render(request, "app.html")


def register(request):
    form = RegistrationForm(
        request.POST or None, initial={"role": request.GET.get("role", "volunteer")}
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = form.save()
        login(request, user)
        return redirect("/")
    return render(request, "registration/register.html", {"form": form})


def access(request):
    return render(request, "registration/access.html")


def worker(request):
    response = HttpResponse(
        (settings.BASE_DIR / "static/resilio/sw.js").read_text(),
        content_type="application/javascript",
    )
    response["Cache-Control"] = "no-cache"
    response["Service-Worker-Allowed"] = "/"
    return response


def record(obj, kind):
    data = {
        "id": obj.pk,
        "kind": kind,
        "item": obj.item_id,
        "name": obj.item.name,
        "category": obj.item.category.name,
        "unit": obj.item.unit,
        "quantity": str(obj.quantity),
        "area": obj.area,
        "upazila": obj.upazila,
        "pin": f.pin(obj) if kind == "offer" else None,
        "confirmed_at": obj.confirmed_at.isoformat() if obj.confirmed_at else None,
        "fresh": bool(
            obj.confirmed_at
            and obj.confirmed_at >= timezone.now() - timedelta(hours=24)
        ),
        "district": obj.district_id,
        "district_name": obj.district.name if obj.district_id else None,
        "division": obj.district.division_id if obj.district_id else None,
        "description": obj.description,
        "status": obj.status,
        "created_at": obj.created_at.isoformat(),
        "updated_at": obj.updated_at.isoformat(),
        "demo": obj.demo,
    }
    # Public board deliberately omits usernames/account identifiers.
    if kind == "offer":
        data.update(
            available=str(obj.available),
            expires_at=obj.expires_at.isoformat() if obj.expires_at else None,
        )
    else:
        data.update(
            remaining=str(obj.remaining),
            unallocated=str(obj.unallocated),
            urgency=obj.urgency,
        )
    return data


def public_data():
    offers = [
        record(x, "offer")
        for x in Offer.objects.select_related(
            "item__category", "district__division"
        ).order_by("-created_at")
    ]
    requests = [
        record(x, "request")
        for x in HelpRequest.objects.select_related(
            "item__category", "district__division"
        ).order_by("-created_at")
    ]
    rows = {}
    for rec in offers + requests:
        if rec["status"] != "open":
            continue
        key = (rec["item"], rec["district"], rec["upazila"], rec["area"])
        row = rows.setdefault(
            key,
            {
                "name": rec["name"],
                "unit": rec["unit"],
                "area": rec["area"],
                "upazila": rec["upazila"],
                "district": rec["district"],
                "division": rec["division"],
                "available": 0,
                "needed": 0,
                "unallocated": 0,
            },
        )
        if rec["kind"] == "offer":
            row["available"] += float(rec["available"])
        else:
            row["needed"] += float(rec["remaining"])
            row["unallocated"] += float(rec["unallocated"])
    return {
        "offers": offers,
        "requests": requests,
        "analytics": list(rows.values()),
        "stats": {
            "offers": sum(float(x["available"]) > 0 for x in offers),
            "requests": sum(x["status"] == "open" for x in requests),
            "urgent": sum(
                x["status"] == "open" and x["urgency"] != "normal" for x in requests
            ),
            "deliveries": Delivery.objects.count(),
        },
        "shelters": [
            {
                "id": x.pk,
                "name": x.name,
                "area": x.area,
                "upazila": x.upazila,
                "pin": f.pin(x),
                "district": x.district_id,
                "district_name": x.district.name if x.district_id else None,
                "division": x.district.division_id if x.district_id else None,
                "total": x.total,
                "occupied": x.occupied,
                "reserved": x.reserved,
                "available": x.available,
                "description": x.description,
                "demo": x.demo,
            }
            for x in Shelter.objects.select_related("district__division")
        ],
        "items": [
            {"id": x.pk, "name": x.name, "unit": x.unit, "category": x.category.name}
            for x in Item.objects.select_related("category")
        ],
        "announcements": [
            f.announcement_data(x)
            for x in Announcement.objects.filter(
                active=True, expires_at__gt=timezone.now()
            )
            .filter(
                Q(author__is_staff=True)
                | Q(author__profile__role="coordinator", author__profile__approved=True)
            )
            .select_related("author__profile")
            .order_by("-created_at")[:100]
        ],
        "geography": {
            "upazilas": f.directory()["upazilas"],
            "district_bn": f.directory()["district_bn"],
            "divisions": list(
                Division.objects.values("code", "name", "latitude", "longitude")
            ),
            "districts": list(
                District.objects.values(
                    "code", "name", "division_id", "latitude", "longitude"
                )
            ),
        },
        "synced_at": timezone.now().isoformat(),
    }


def private_data(user):
    profile, _ = Profile.objects.get_or_create(user=user)
    assignments = Assignment.objects.select_related(
        "offer__item", "request", "volunteer"
    )
    if not s.coordinator(user):
        assignments = assignments.filter(
            Q(volunteer=user) | Q(request__owner=user) | Q(offer__owner=user)
        )
    result = {
        "user": {
            "id": user.pk,
            "username": user.username,
            "name": user.first_name,
            "email": user.email,
            "area": profile.area,
            "role": profile.role,
            "admin": user.is_staff,
            "organization": profile.organization,
            "approved": profile.approved,
            "can_coordinate": s.coordinator(user),
            "share_presence": profile.share_presence,
            "public_label": profile.public_label,
            "upazila": profile.upazila,
            "district": profile.district_id,
            "division": profile.district.division_id if profile.district_id else None,
            "share_location": profile.share_location,
        },
        "owned_offers": list(
            Offer.objects.filter(owner=user).values_list("pk", flat=True)
        ),
        "owned_requests": list(
            HelpRequest.objects.filter(owner=user).values_list("pk", flat=True)
        ),
        "assignments": [
            {
                "id": x.pk,
                "offer": x.offer_id,
                "request": x.request_id,
                "name": x.offer.item.name,
                "unit": x.offer.item.unit,
                "quantity": str(x.quantity),
                "delivered_quantity": str(x.delivered_quantity),
                "status": x.status,
                "volunteer": x.volunteer.username,
                "volunteer_id": x.volunteer_id,
                "requester_id": x.request.owner_id,
            }
            for x in assignments
        ],
        "notifications": list(
            Notification.objects.filter(user=user)
            .order_by("-created_at")
            .values("id", "text", "read", "created_at")[:100]
        ),
    }
    result.update(f.private_extensions(user))
    if s.coordinator(user):
        result["volunteers"] = list(
            User.objects.filter(is_active=True, profile__role="volunteer").values(
                "id", "username"
            )
        )
    if user.is_staff:
        result["officers"] = list(
            Profile.objects.filter(role="coordinator")
            .select_related("user")
            .values("id", "user__username", "organization", "area", "approved")
        )
        result["reports"] = list(
            Report.objects.order_by("-created_at").values(
                "id", "reason", "decision", "offer_id", "request_id", "reviewed_at"
            )[:100]
        )
        result["audit"] = list(
            Audit.objects.order_by("-created_at").values(
                "id", "actor__username", "action", "target", "detail", "created_at"
            )[:100]
        )
    return result


@never_cache
def api(request, action):
    try:
        if request.method == "GET":
            if action == "public":
                response = JsonResponse(public_data())
                response["X-Resilio-Public"] = "1"
                return response
            if not request.user.is_authenticated:
                return JsonResponse({"error": "Sign in to continue."}, status=401)
            if action == "me":
                return JsonResponse(private_data(request.user))
            if action == "messages":
                return JsonResponse(
                    f.messages(
                        request.user,
                        request.GET.get("assignment"),
                        request.GET.get("before"),
                    )
                )
            if action == "presence":
                cutoff = timezone.now() - timedelta(seconds=75)
                people = Profile.objects.filter(
                    share_presence=True, last_seen__gte=cutoff, user__is_active=True
                ).select_related("user", "district__division")
                return JsonResponse(
                    {
                        "participants": [
                            {
                                "key": f"participant-{p.pk}",
                                "label": p.public_label or f"Participant {p.pk}",
                                "role": (
                                    "administrator"
                                    if p.user.is_staff
                                    else (
                                        "officer applicant"
                                        if p.role == "coordinator" and not p.approved
                                        else p.get_role_display()
                                    )
                                ),
                                "area": p.area or "area not set",
                                "organization": (
                                    p.organization
                                    if p.role == "coordinator" and p.approved
                                    else ""
                                ),
                                "last_seen": p.last_seen.isoformat(),
                                "upazila": p.upazila,
                                "district": p.district_id,
                                "division": (
                                    p.district.division_id if p.district_id else None
                                ),
                                "location": shared_location(p),
                            }
                            for p in people
                        ],
                        "window_seconds": 75,
                        "server_time": timezone.now().isoformat(),
                    }
                )
            if action == "matches":
                req = HelpRequest.objects.select_related("item").get(
                    pk=request.GET.get("request")
                )
                found = []
                if req.status == "open" and req.unallocated > 0:
                    for x in Offer.objects.filter(
                        item=req.item, status="open"
                    ).select_related("item__category", "district__division"):
                        if x.available <= 0:
                            continue
                        row = record(x, "offer")
                        row["max_quantity"] = str(min(x.available, req.unallocated))
                        row["reasons"] = [
                            (
                                "Same area"
                                if x.area == req.area
                                and (
                                    not x.district_id
                                    or not req.district_id
                                    or x.district_id == req.district_id
                                )
                                else "Different area — coordinate transport"
                            ),
                            (
                                "Can fully cover unallocated need"
                                if x.available >= req.unallocated
                                else "Can partially fulfil this request"
                            ),
                        ]
                        if req.district_id and x.district_id:
                            row["reasons"].append(
                                "Same district"
                                if x.district_id == req.district_id
                                else "Different district — coordinate transport"
                            )
                        if req.upazila and x.upazila and req.upazila == x.upazila:
                            row["reasons"].append("Same upazila")
                        if x.expires_at:
                            row["reasons"].append("Expires " + x.expires_at.isoformat())
                        found.append(row)
                found.sort(
                    key=lambda x: (
                        bool(req.district_id) and x["district"] != req.district_id,
                        bool(req.upazila) and x["upazila"] != req.upazila,
                        x["area"] != req.area,
                        x["expires_at"] or "9999",
                        -float(x["available"]),
                    )
                )
                return JsonResponse({"matches": found})
            return JsonResponse({"error": "Unknown endpoint."}, status=404)
        if request.method != "POST":
            return JsonResponse({"error": "Method not allowed."}, status=405)
        if not request.user.is_authenticated:
            return JsonResponse({"error": "Sign in to continue."}, status=401)
        data = json.loads(request.body or "{}")
        if not isinstance(data, dict):
            raise ValueError()
        user = request.user
        # Serialize operational reads+writes on SQLite and PostgreSQL.
        with transaction.atomic():
            s.acquire_write_lock()
            result = {}
            if action in [
                "emergency",
                "announcement",
                "message",
                "reconfirm",
                "shelter_place",
            ]:
                handler = {
                    "emergency": f.emergency,
                    "announcement": f.announcement,
                    "message": f.send_message,
                    "reconfirm": f.reconfirm,
                    "shelter_place": f.shelter_place,
                }[action]
                obj = handler(user, data)
                result = {"id": obj.pk}
            elif action == "resource":
                obj, created = s.resource(user, data)
                result = {"id": obj.pk, "saved": created}
            elif action == "cancel":
                s.cancel_resource(user, data)
            elif action == "reserve":
                result = {"id": s.reserve(user, data).pk}
            elif action == "transition":
                result = {"id": s.transition(user, data).pk}
            elif action == "shelter":
                result = {"id": s.shelter(user, data).pk}
            elif action == "report":
                result = {"id": s.report(user, data).pk}
            elif action == "review":
                result = {"id": s.review(user, data).pk}
            elif action == "approve":
                s.approve_officer(user, data)
            elif action == "location":
                s.location_update(user, data)
            elif action == "presence":
                profile, _ = Profile.objects.get_or_create(user=user)
                if "enabled" in data:
                    if type(data["enabled"]) is not bool:
                        s.fail("Choose an enabled state.")
                    profile.share_presence = data["enabled"]
                    if not profile.share_presence:
                        s.clear_location(profile)
                    s.audit(
                        user,
                        "presence sharing updated",
                        profile,
                        str(profile.share_presence),
                    )
                if "label" in data:
                    profile.public_label = s.text(data, "label", 40, False)
                profile.last_seen = timezone.now() if profile.share_presence else None
                profile.save(
                    update_fields=[
                        "share_presence",
                        "public_label",
                        "last_seen",
                        "share_location",
                        "latitude",
                        "longitude",
                        "location_accuracy",
                        "location_updated_at",
                    ]
                )
                result = {"enabled": profile.share_presence}
            elif action == "read":
                Notification.objects.filter(user=user, pk=data.get("id")).update(
                    read=True
                )
            elif action == "profile":
                user.first_name = s.text(data, "name", 150, False)
                user.email = s.text(data, "email", 254, False)
                from django.core.validators import validate_email

                if user.email:
                    validate_email(user.email)
                user.save(update_fields=["first_name", "email"])
                profile, _ = Profile.objects.get_or_create(user=user)
                profile.area = s.area(s.text(data, "area", 100, False))
                if "district" in data:
                    profile.district = s.validated_district(data)
                profile.upazila = f.locality(data, profile.district_id)
                profile.save()
                s.audit(user, "profile updated", profile)
            else:
                return JsonResponse({"error": "Unknown endpoint."}, status=404)
        return JsonResponse({"ok": True, **result})
    except PermissionDenied as exc:
        return JsonResponse({"error": str(exc)}, status=403)
    except ValidationError as exc:
        fields = exc.message_dict if hasattr(exc, "message_dict") else {}
        return JsonResponse(
            {"error": " ".join(exc.messages), "fields": fields}, status=400
        )
    except ObjectDoesNotExist:
        return JsonResponse({"error": "Record not found."}, status=404)
    except (ValueError, TypeError, KeyError, json.JSONDecodeError):
        return JsonResponse(
            {"error": "Invalid input. Check the form and try again."}, status=400
        )
    except (OperationalError, IntegrityError):
        return JsonResponse(
            {
                "error": "Another update conflicted with this action. Refresh and retry; your local entry is preserved."
            },
            status=409,
        )


def shared_location(profile):
    if (
        not profile.share_presence
        or not profile.share_location
        or profile.latitude is None
        or profile.longitude is None
        or not profile.location_updated_at
        or profile.location_updated_at < timezone.now() - timedelta(minutes=5)
    ):
        return None
    return {
        "latitude": float(profile.latitude),
        "longitude": float(profile.longitude),
        "accuracy": profile.location_accuracy,
        "updated_at": profile.location_updated_at.isoformat(),
        "source": "browser-reported",
    }
