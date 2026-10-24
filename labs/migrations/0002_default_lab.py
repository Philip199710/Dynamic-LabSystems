"""Create the first lab (the existing South Sudan lab) and move everything
that already exists into it: samples, instruments, chat channels, clients and
every staff login (Dynamic admins and client-portal accounts excluded)."""

from django.db import migrations


def forwards(apps, schema_editor):
    Lab = apps.get_model("labs", "Lab")
    LabMember = apps.get_model("labs", "LabMember")
    User = apps.get_model("auth", "User")
    lab, _ = Lab.objects.get_or_create(
        code="SSD-01",
        defaults={"name": "South Sudan Lab", "country": "South Sudan", "max_logins": 10, "devices_per_login": 1},
    )
    for model in [("samples", "Sample"), ("catalog", "Instrument"), ("chat", "Channel"), ("accounts", "Client")]:
        apps.get_model(*model).objects.filter(lab__isnull=True).update(lab=lab)
    for user in User.objects.filter(is_superuser=False, client_profile__isnull=True).exclude(groups__name="Dynamic Admin"):
        LabMember.objects.get_or_create(user=user, defaults={"lab": lab})


class Migration(migrations.Migration):
    dependencies = [
        ("labs", "0001_initial"),
        ("samples", "0005_sample_lab"),
        ("catalog", "0015_instrument_lab"),
        ("chat", "0003_channel_lab_alter_channel_name_and_more"),
        ("accounts", "0003_client_lab"),
    ]
    operations = [migrations.RunPython(forwards, migrations.RunPython.noop)]
