from django.db import migrations


def seed_categories(apps, schema_editor):
    category = apps.get_model("assets", "Category")
    for name, kind in [
        ("PC de escritorio", "PC"),
        ("Laptop", "LAPTOP"),
        ("Router", "ROUTER"),
        ("Impresora", "IMPRESORA"),
        ("Monitor", "MONITOR"),
        ("Otros", "OTROS"),
    ]:
        category.objects.using(schema_editor.connection.alias).get_or_create(
            name=name, defaults={"kind": kind}
        )


class Migration(migrations.Migration):
    dependencies = [("assets", "0001_initial")]
    operations = [migrations.RunPython(seed_categories, migrations.RunPython.noop)]
