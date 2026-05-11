from django.db import migrations, models
from django.utils import timezone


def mark_existing_users_as_plan_selected(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    User.objects.filter(plan_selected_at__isnull=True).update(plan_selected_at=timezone.now())


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0004_user_paid_plan_started_at"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="plan_selected_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(mark_existing_users_as_plan_selected, migrations.RunPython.noop),
    ]
