import os
from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth import get_user_model
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.db import transaction
from coordination.models import Profile
from coordination.services import acquire_write_lock, audit


class Command(BaseCommand):
    help = "Create ONE new administrator from environment values. Never promote or reset an existing account."

    @transaction.atomic
    def handle(self, *args, **options):
        username = os.getenv("RESILIO_ADMIN_USERNAME", "").strip()
        password = os.getenv("RESILIO_ADMIN_PASSWORD", "")
        if not username and not password:
            self.stdout.write("Admin bootstrap skipped (no bootstrap credentials).")
            return
        if not username or not password:
            raise CommandError(
                "Set both RESILIO_ADMIN_USERNAME and RESILIO_ADMIN_PASSWORD, or remove both."
            )
        acquire_write_lock()
        User = get_user_model()
        existing = User.objects.filter(username=username).first()
        if existing:
            if not existing.is_superuser:
                raise CommandError(
                    "Bootstrap username already belongs to a non-administrator. Choose a different name. No privileges were changed."
                )
            self.stdout.write(
                "Existing administrator preserved; password was not changed."
            )
            return
        user = User(
            username=username,
            email=os.getenv("RESILIO_ADMIN_EMAIL", "").strip(),
            is_staff=True,
            is_superuser=True,
        )
        try:
            validate_password(password, user=user)
            if len(password) < 12:
                raise ValidationError(
                    "Use at least 12 characters for the hosted administrator."
                )
            user.full_clean(exclude=["password"])
        except ValidationError as e:
            raise CommandError("Administrator setup: " + " ".join(e.messages))
        user.set_password(password)
        user.save()
        Profile.objects.create(user=user)
        audit(user, "hosted administrator created", user)
        self.stdout.write(
            "Administrator created. Remove bootstrap environment values after the first successful deploy."
        )
