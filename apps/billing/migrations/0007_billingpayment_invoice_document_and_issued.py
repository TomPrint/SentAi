import django.core.validators
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0006_billingpayment_invoice_tracking"),
    ]

    operations = [
        migrations.AddField(
            model_name="billingpayment",
            name="invoice_document",
            field=models.FileField(blank=True, upload_to="invoices/%Y/%m/", validators=[django.core.validators.FileExtensionValidator(["pdf"])]),
        ),
        migrations.AddField(
            model_name="billingpayment",
            name="invoice_issued",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="billingpayment",
            name="invoice_issued_at",
            field=models.DateField(blank=True, null=True),
        ),
    ]
