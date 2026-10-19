from django.db import migrations


def create(apps, schema_editor):
    apps.get_model("auth", "Group").objects.get_or_create(name="Dynamic Admin")


class Migration(migrations.Migration):
    dependencies = [("accounts", "0001_initial"), ("auth", "0012_alter_user_first_name_max_length")]
    operations = [migrations.RunPython(create, migrations.RunPython.noop)]
