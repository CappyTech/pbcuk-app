from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("quotes", "0011_quote_reference_blank"),
    ]

    operations = [
        migrations.AddField(
            model_name="invoice",
            name="client_phone",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="invoice",
            name="items_in_stock_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="build_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="invoice",
            name="shipping_date",
            field=models.DateField(blank=True, null=True),
        ),
        migrations.CreateModel(
            name="InvoiceEvent",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("type", models.CharField(choices=[("paid", "Paid"), ("stock_ok", "Items in stock"), ("build_scheduled", "Build scheduled"), ("ship_scheduled", "Shipping scheduled")], max_length=50)),
                ("message", models.CharField(blank=True, max_length=255)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("invoice", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="events", to="quotes.invoice")),
            ],
        ),
    ]
