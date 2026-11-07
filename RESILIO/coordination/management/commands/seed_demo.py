from django.core.management.base import BaseCommand, CommandError
from django.contrib.auth.models import User
from django.db import transaction
from coordination.models import Category, Item, Profile, Offer, HelpRequest, Shelter


class Command(BaseCommand):
    help = "Create labelled fictional data; repeat runs never reset users or inventory."

    def add_arguments(self, parser):
        parser.add_argument(
            "--password",
            required=True,
            help="Password for NEW fictional users only; never creates staff accounts.",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        from coordination.services import acquire_write_lock

        acquire_write_lock()
        password = options["password"]
        if len(password) < 12:
            raise CommandError("Use a demo password of at least 12 characters.")
        catalog = [
            ("water", "Drinking water", "L"),
            ("water", "Purification tablets", "tablets"),
            ("food", "Food rations", "packs"),
            ("food", "Rice", "kg"),
            ("medical", "First aid kits", "kits"),
            ("medical", "Face masks", "pieces"),
            ("shelter", "Blankets", "pieces"),
            ("shelter", "Tents", "tents"),
        ]
        for category, name, unit in catalog:
            c, _ = Category.objects.get_or_create(name=category)
            Item.objects.get_or_create(
                name=name, defaults={"category": c, "unit": unit}
            )
        users = {}
        for username, role in [
            ("demo_requester", "community"),
            ("demo_donor", "community"),
            ("demo_volunteer", "volunteer"),
            ("demo_officer", "coordinator"),
        ]:
            user, created = User.objects.get_or_create(
                username=username,
                defaults={"first_name": username.replace("demo_", "").title()},
            )
            if created:
                user.set_password(password)
                user.save()
                Profile.objects.create(
                    user=user,
                    role=role,
                    area="mirpur",
                    organization=(
                        "Demo Relief Organization" if role == "coordinator" else ""
                    ),
                )
            users[username] = user
        water = Item.objects.get(name="Drinking water")
        Offer.objects.get_or_create(
            owner=users["demo_donor"],
            item=water,
            demo=True,
            defaults={
                "quantity": 50,
                "area": "mirpur",
                "description": "Fictional demonstration drinking water supply.",
            },
        )
        HelpRequest.objects.get_or_create(
            owner=users["demo_requester"],
            item=water,
            demo=True,
            defaults={
                "quantity": 20,
                "area": "mirpur",
                "urgency": "urgent",
                "description": "Fictional acceptance scenario: 20 L needed.",
            },
        )
        for name, amount, loc in [
            ("Food rations", 80, "uttara"),
            ("First aid kits", 8, "mirpur"),
            ("Blankets", 40, "uttara"),
        ]:
            Offer.objects.get_or_create(
                owner=users["demo_donor"],
                item=Item.objects.get(name=name),
                demo=True,
                defaults={
                    "quantity": amount,
                    "area": loc,
                    "description": "Fictional demonstration supply.",
                },
            )
        Shelter.objects.get_or_create(
            name="Demo Community Hall",
            defaults={
                "area": "mirpur",
                "total": 100,
                "occupied": 20,
                "reserved": 10,
                "description": "Fictional shelter for coursework.",
                "demo": True,
            },
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Demo catalog and fictional accounts ready. Existing accounts, passwords and records were preserved. No administrator was created."
            )
        )
