# Generated manually for Sam's payment-traceability branch

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
        (
            "core",
            "0003_alter_category_options_alter_order_options_and_more",
        ),
    ]

    operations = [
        migrations.CreateModel(
            name="TraceabilityRecord",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("order_reference", models.CharField(max_length=20)),
                ("product_name_snapshot", models.CharField(max_length=120)),
                (
                    "product_category_snapshot",
                    models.CharField(blank=True, max_length=50),
                ),
                ("producer_name_snapshot", models.CharField(max_length=100)),
                (
                    "producer_postcode_snapshot",
                    models.CharField(max_length=10),
                ),
                (
                    "customer_postcode_snapshot",
                    models.CharField(blank=True, max_length=10),
                ),
                (
                    "food_miles",
                    models.DecimalField(
                        decimal_places=1, default=0, max_digits=6
                    ),
                ),
                (
                    "allergen_info_snapshot",
                    models.TextField(blank=True),
                ),
                (
                    "organic_certified",
                    models.BooleanField(default=False),
                ),
                (
                    "harvest_date",
                    models.DateField(blank=True, null=True),
                ),
                (
                    "best_before_date",
                    models.DateField(blank=True, null=True),
                ),
                (
                    "quantity",
                    models.PositiveIntegerField(default=1),
                ),
                (
                    "unit_price",
                    models.DecimalField(decimal_places=2, max_digits=10),
                ),
                (
                    "line_total",
                    models.DecimalField(decimal_places=2, max_digits=10),
                ),
                (
                    "created_at",
                    models.DateTimeField(auto_now_add=True),
                ),
                (
                    "customer",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="traceability_records",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "order_item",
                    models.OneToOneField(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="traceability_record",
                        to="core.orderitem",
                    ),
                ),
                (
                    "producer",
                    models.ForeignKey(
                        null=True,
                        on_delete=django.db.models.deletion.SET_NULL,
                        related_name="traceability_records",
                        to="core.producer",
                    ),
                ),
            ],
            options={
                "ordering": ("-created_at",),
            },
        ),
    ]
