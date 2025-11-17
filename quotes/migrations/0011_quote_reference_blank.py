from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        ('quotes', '0010_invoice_user_fk'),
    ]

    operations = [
        migrations.AlterField(
            model_name='quote',
            name='reference',
            field=models.CharField(blank=True, max_length=30, unique=True),
        ),
    ]
