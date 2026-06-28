import django.core.validators
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("billing", "0007_billingpayment_invoice_document_and_issued"),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="BillingInvoice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("invoice_number", models.CharField(max_length=100)),
                ("issued_at", models.DateField()),
                ("document", models.FileField(upload_to="invoices/%Y/%m/", validators=[django.core.validators.FileExtensionValidator(["pdf"])])),
                ("sent", models.BooleanField(default=False)),
                ("sent_at", models.DateField(blank=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("subscription", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="invoices", to="billing.billingsubscription")),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="billing_invoices", to=settings.AUTH_USER_MODEL)),
            ],
            options={"ordering": ["-issued_at", "-created_at"]},
        ),
    ]
