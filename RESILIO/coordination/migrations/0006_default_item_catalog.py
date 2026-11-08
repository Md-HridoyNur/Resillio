from django.db import migrations

# Frozen defaults for fresh installs. Existing catalog definitions are preserved.
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


def seed_catalog(apps, schema_editor):
    Category = apps.get_model("coordination", "Category")
    Item = apps.get_model("coordination", "Item")
    alias = schema_editor.connection.alias
    for category, name, unit in CATALOG:
        c, _ = Category.objects.using(alias).get_or_create(name=category)
        Item.objects.using(alias).get_or_create(
            name=name, defaults={"category": c, "unit": unit}
        )


class Migration(migrations.Migration):
    dependencies = [("coordination", "0005_field_coordination")]
    operations = [migrations.RunPython(seed_catalog, migrations.RunPython.noop)]
