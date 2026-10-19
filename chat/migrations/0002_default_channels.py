from django.db import migrations

DEFAULTS = [
    ("general", "Whole-lab announcements and day-to-day chat"),
    ("sample-intake", "Arrivals, tanker drops and storage questions"),
    ("results-qa", "Result checks, retests and COA sign-off"),
]


def create(apps, schema_editor):
    Channel = apps.get_model("chat", "Channel")
    for name, description in DEFAULTS:
        Channel.objects.get_or_create(name=name, defaults={"description": description})


class Migration(migrations.Migration):
    dependencies = [("chat", "0001_initial")]
    operations = [migrations.RunPython(create, migrations.RunPython.noop)]
