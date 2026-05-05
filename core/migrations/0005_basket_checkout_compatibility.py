# Generated during basket checkout merge conflict resolution.

import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0004_traceabilityrecord"),
    ]

    operations = [
        migrations.AddField(
            model_name="order",
            name="collection_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="confirmed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="order",
            name="delivery_address",
            field=models.TextField(blank=True),
        ),
        migrations.AlterField(
            model_name="order",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("confirmed", "Confirmed"),
                    ("processing", "Processing"),
                    ("ready", "Ready for Collection"),
                    ("delivered", "Delivered"),
                    ("cancelled", "Cancelled"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="completed_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="payment",
            name="status",
            field=models.CharField(
                choices=[
                    ("pending", "Pending"),
                    ("completed", "Completed"),
                    ("failed", "Failed"),
                    ("refunded", "Refunded"),
                ],
                default="pending",
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="payment",
            name="stripe_charge_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AddField(
            model_name="payment",
            name="stripe_payment_intent_id",
            field=models.CharField(blank=True, max_length=255),
        ),
        migrations.AlterField(
            model_name="payment",
            name="order",
            field=models.OneToOneField(
                on_delete=django.db.models.deletion.CASCADE,
                related_name="payment",
                to="core.order",
            ),
        ),
    ]
