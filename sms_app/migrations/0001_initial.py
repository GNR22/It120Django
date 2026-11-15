from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = []

    operations = [
        migrations.CreateModel(
            name="SMSMessage",
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
                ("recipient", models.CharField(max_length=20)),
                ("body", models.TextField()),
                (
                    "outcome",
                    models.CharField(
                        choices=[("submitted", "Submitted"), ("failed", "Failed")],
                        max_length=10,
                    ),
                ),
                ("provider_sid", models.CharField(blank=True, max_length=64)),
                ("provider_status", models.CharField(blank=True, max_length=30)),
                ("error_code", models.CharField(blank=True, max_length=20)),
                ("error_message", models.CharField(blank=True, max_length=300)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("status_updated_at", models.DateTimeField(blank=True, null=True)),
            ],
            options={
                "ordering": ["-created_at"],
            },
        ),
    ]
