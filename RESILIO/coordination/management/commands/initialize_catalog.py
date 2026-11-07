from django.core.management.base import BaseCommand
from django.db import transaction
from coordination.models import Category, Item
from coordination.services import acquire_write_lock

CATALOG = [
    ("water", "Drinking water", "L"),
    ("water", "Purification tablets", "tablets"),
    ("food", "Food rations", "packs"),
    ("food", "Rice", "kg"),
    ("medical", "First aid kits", "kits"),
    ("medical", "Face masks", "pieces"),
    ("shelter", "Blankets", "pieces"),
    ("shelter", "Tents", "tents"),
]


class Command(BaseCommand):
    help = "Initialize canonical items without creating public demo accounts or stock."

    @transaction.atomic
    def handle(self, *args, **options):
        acquire_write_lock()
        for category, name, unit in CATALOG:
            c, _ = Category.objects.get_or_create(name=category)
            Item.objects.get_or_create(
                name=name, defaults={"category": c, "unit": unit}
            )
        self.stdout.write(
            "Canonical catalog ready. No demonstration users were created."
        )
