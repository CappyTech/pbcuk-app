from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0002_companydetails"),
    ]

    operations = [
        migrations.AddField(
            model_name="companydetails",
            name="bank_name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="companydetails",
            name="account_name",
            field=models.CharField(blank=True, max_length=200),
        ),
        migrations.AddField(
            model_name="companydetails",
            name="account_number",
            field=models.CharField(blank=True, max_length=50),
        ),
        migrations.AddField(
            model_name="companydetails",
            name="sort_code",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name="companydetails",
            name="iban",
            field=models.CharField(blank=True, max_length=34),
        ),
        migrations.AddField(
            model_name="companydetails",
            name="bic",
            field=models.CharField(blank=True, max_length=11),
        ),
    ]
