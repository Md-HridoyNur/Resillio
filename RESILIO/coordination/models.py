from django.conf import settings
from django.db import models
from django.db.models import Q, F
from django.utils import timezone
from decimal import Decimal

U = settings.AUTH_USER_MODEL
ACTIVE = ["assigned", "in_progress", "awaiting_confirmation"]


class Division(models.Model):
    code = models.SlugField(max_length=32, primary_key=True)
    name = models.CharField(max_length=60, unique=True)
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class District(models.Model):
    code = models.SlugField(max_length=40, primary_key=True)
    name = models.CharField(max_length=80, unique=True)
    division = models.ForeignKey(
        Division, on_delete=models.PROTECT, related_name="districts"
    )
    latitude = models.FloatField()
    longitude = models.FloatField()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name


class Profile(models.Model):
    upazila = models.CharField(max_length=20, blank=True)
    user = models.OneToOneField(U, on_delete=models.CASCADE)
    role = models.CharField(
        max_length=12,
        choices=[
            ("community", "Community / Donor"),
            ("volunteer", "Volunteer"),
            ("coordinator", "NGO / Relief Officer"),
        ],
        default="community",
    )
    area = models.CharField(max_length=100, blank=True)
    organization = models.CharField(max_length=120, blank=True)
    approved = models.BooleanField(default=False)
    share_presence = models.BooleanField(default=False)
    public_label = models.CharField(max_length=40, blank=True)
    last_seen = models.DateTimeField(null=True, blank=True, db_index=True)
    district = models.ForeignKey(
        District, on_delete=models.PROTECT, null=True, blank=True
    )
    share_location = models.BooleanField(default=False)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True
    )
    location_accuracy = models.FloatField(null=True, blank=True)
    location_updated_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(
                        latitude__isnull=True,
                        longitude__isnull=True,
                        location_accuracy__isnull=True,
                        location_updated_at__isnull=True,
                    )
                    | Q(
                        latitude__isnull=False,
                        longitude__isnull=False,
                        location_accuracy__isnull=False,
                        latitude__gte=-90,
                        latitude__lte=90,
                        longitude__gte=-180,
                        longitude__lte=180,
                        location_accuracy__gte=0,
                        location_accuracy__lte=100000,
                        location_updated_at__isnull=False,
                    )
                ),
                name="profile_location_bounds",
            )
        ]


class Category(models.Model):
    name = models.CharField(max_length=40, unique=True)

    def __str__(self):
        return self.name


class Item(models.Model):
    name = models.CharField(max_length=80, unique=True)
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    unit = models.CharField(max_length=20)

    def __str__(self):
        return f"{self.name} ({self.unit})"


class Record(models.Model):
    upazila = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True
    )
    pin_label = models.CharField(max_length=160, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    district = models.ForeignKey(
        District, on_delete=models.PROTECT, null=True, blank=True
    )
    item = models.ForeignKey(Item, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    area = models.CharField(max_length=100, db_index=True)
    description = models.TextField(blank=True, max_length=2000)
    owner = models.ForeignKey(U, on_delete=models.PROTECT)
    status = models.CharField(
        max_length=12,
        default="open",
        choices=[
            ("open", "Open"),
            ("cancelled", "Cancelled"),
            ("fulfilled", "Fulfilled"),
        ],
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    demo = models.BooleanField(default=False)

    class Meta:
        abstract = True
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(latitude__isnull=True, longitude__isnull=True)
                    | Q(
                        latitude__isnull=False,
                        longitude__isnull=False,
                        latitude__gte=-90,
                        latitude__lte=90,
                        longitude__gte=-180,
                        longitude__lte=180,
                    )
                ),
                name="%(class)s_pin_bounds",
            ),
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="%(class)s_positive"
            ),
        ]


class Offer(Record):
    expires_at = models.DateTimeField(null=True, blank=True)

    @property
    def available(self):
        if self.status != "open" or (
            self.expires_at and self.expires_at <= timezone.now()
        ):
            return Decimal(0)
        return self.quantity - allocated(self.assignments)


class HelpRequest(Record):
    urgency = models.CharField(
        max_length=10,
        default="normal",
        choices=[("normal", "Normal"), ("urgent", "Urgent"), ("critical", "Critical")],
    )
    client_id = models.UUIDField(null=True, blank=True)

    class Meta(Record.Meta):
        constraints = Record.Meta.constraints + [
            models.UniqueConstraint(
                fields=["owner", "client_id"], name="owner_client_id_unique"
            )
        ]

    @property
    def delivered(self):
        return self.assignments.filter(status="delivered").aggregate(
            n=models.Sum("delivered_quantity")
        )["n"] or Decimal(0)

    @property
    def remaining(self):
        return max(Decimal(0), self.quantity - self.delivered)

    @property
    def unallocated(self):
        return (
            max(Decimal(0), self.quantity - allocated(self.assignments))
            if self.status == "open"
            else Decimal(0)
        )


def allocated(query):
    active = query.filter(status__in=ACTIVE).aggregate(n=models.Sum("quantity"))[
        "n"
    ] or Decimal(0)
    done = query.filter(status="delivered").aggregate(
        n=models.Sum("delivered_quantity")
    )["n"] or Decimal(0)
    return active + done


class Assignment(models.Model):
    offer = models.ForeignKey(
        Offer, on_delete=models.PROTECT, related_name="assignments"
    )
    request = models.ForeignKey(
        HelpRequest, on_delete=models.PROTECT, related_name="assignments"
    )
    volunteer = models.ForeignKey(U, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    delivered_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    status = models.CharField(
        max_length=24,
        default="assigned",
        choices=[
            (x, x.replace("_", " ").title())
            for x in ACTIVE + ["delivered", "cancelled"]
        ],
        db_index=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(quantity__gt=0), name="assignment_positive"
            ),
            models.CheckConstraint(
                condition=Q(delivered_quantity__gte=0)
                & Q(delivered_quantity__lte=F("quantity")),
                name="delivery_bounds",
            ),
        ]


class Delivery(models.Model):
    assignment = models.OneToOneField(Assignment, on_delete=models.PROTECT)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    confirmed_by = models.ForeignKey(U, on_delete=models.PROTECT)
    confirmed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.CheckConstraint(condition=Q(quantity__gt=0), name="receipt_positive")
        ]


class Notification(models.Model):
    user = models.ForeignKey(U, on_delete=models.CASCADE)
    text = models.CharField(max_length=500)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)


class Report(models.Model):
    reporter = models.ForeignKey(U, on_delete=models.PROTECT)
    offer = models.ForeignKey(Offer, null=True, blank=True, on_delete=models.PROTECT)
    request = models.ForeignKey(
        HelpRequest, null=True, blank=True, on_delete=models.PROTECT
    )
    reason = models.CharField(max_length=500)
    decision = models.CharField(max_length=500, blank=True)
    reviewed_by = models.ForeignKey(
        U,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="reviewed_reports",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(offer__isnull=False, request__isnull=True)
                    | Q(offer__isnull=True, request__isnull=False)
                ),
                name="report_one_target",
            )
        ]


class Shelter(models.Model):
    upazila = models.CharField(max_length=20, blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True
    )
    pin_label = models.CharField(max_length=160, blank=True)

    district = models.ForeignKey(
        District, on_delete=models.PROTECT, null=True, blank=True
    )
    name = models.CharField(max_length=120, unique=True)
    area = models.CharField(max_length=100, db_index=True)
    total = models.PositiveIntegerField()
    occupied = models.PositiveIntegerField(default=0)
    reserved = models.PositiveIntegerField(default=0)
    description = models.TextField(blank=True, max_length=2000)
    demo = models.BooleanField(default=False)

    @property
    def available(self):
        return self.total - self.occupied - self.reserved

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(total__gte=F("occupied") + F("reserved")),
                name="shelter_capacity",
            ),
            models.CheckConstraint(
                condition=(
                    Q(latitude__isnull=True, longitude__isnull=True)
                    | Q(
                        latitude__isnull=False,
                        longitude__isnull=False,
                        latitude__gte=-90,
                        latitude__lte=90,
                        longitude__gte=-180,
                        longitude__lte=180,
                    )
                ),
                name="%(class)s_pin_bounds",
            ),
        ]


class Audit(models.Model):
    actor = models.ForeignKey(U, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=60)
    target = models.CharField(max_length=120)
    detail = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class CoordinationLock(models.Model):
    """Singleton mutex for cross-record invariants on PostgreSQL deployments."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1, editable=False)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=Q(id=1), name="coordination_lock_singleton"
            )
        ]


class EmergencyCase(models.Model):
    owner = models.ForeignKey(
        U, on_delete=models.PROTECT, related_name="emergency_cases"
    )
    district = models.ForeignKey(District, on_delete=models.PROTECT)
    upazila = models.CharField(max_length=20, blank=True)
    area = models.CharField(max_length=100)
    kind = models.CharField(
        max_length=20,
        choices=[
            (x, x.title())
            for x in ["medical", "trapped", "evacuation", "flood", "other"]
        ],
    )
    people = models.PositiveIntegerField()
    description = models.TextField(max_length=2000)
    contact = models.CharField(max_length=80, blank=True)
    latitude = models.DecimalField(
        max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=6, null=True, blank=True
    )
    pin_label = models.CharField(max_length=160, blank=True)
    status = models.CharField(
        max_length=20,
        default="received",
        choices=[
            (x, x.replace("_", " ").title())
            for x in ["received", "acknowledged", "assigned", "resolved", "cancelled"]
        ],
    )
    assigned_to = models.ForeignKey(
        U,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="emergency_assignments",
    )
    client_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.CheckConstraint(
                condition=(
                    Q(latitude__isnull=True, longitude__isnull=True)
                    | Q(
                        latitude__isnull=False,
                        longitude__isnull=False,
                        latitude__gte=-90,
                        latitude__lte=90,
                        longitude__gte=-180,
                        longitude__lte=180,
                    )
                ),
                name="%(class)s_pin_bounds",
            ),
            models.UniqueConstraint(
                fields=["owner", "client_id"], name="emergency_client_unique"
            ),
            models.CheckConstraint(
                condition=Q(people__gte=1, people__lte=10000),
                name="emergency_people_bounds",
            ),
        ]


class Announcement(models.Model):
    author = models.ForeignKey(U, on_delete=models.PROTECT)
    district = models.ForeignKey(
        District, null=True, blank=True, on_delete=models.PROTECT
    )
    title = models.CharField(max_length=160)
    body = models.TextField(max_length=3000)
    expires_at = models.DateTimeField()
    active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)


class AssignmentMessage(models.Model):
    assignment = models.ForeignKey(
        Assignment, on_delete=models.PROTECT, related_name="messages"
    )
    sender = models.ForeignKey(U, on_delete=models.PROTECT)
    body = models.TextField(max_length=1500)
    client_id = models.UUIDField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["assignment", "sender", "client_id"],
                name="assignment_message_client_unique",
            )
        ]
