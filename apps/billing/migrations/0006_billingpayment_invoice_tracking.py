from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0005_alter_billingprofile_tax_id"),
    ]

    operations = [
        migrations.AddField(
            model_name="billingpayment",
            name="invoice_sent",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="billingpayment",
            name="invoice_sent_at",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="billingpayment",
            name="invoice_number",
            field=models.CharField(blank=True, max_length=100),
        ),
    ]
