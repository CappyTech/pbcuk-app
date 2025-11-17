from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
    ]

    operations = [
        migrations.RunSQL(
            # Case-insensitive unique index using lower(email); works on SQLite & Postgres
            sql="CREATE UNIQUE INDEX IF NOT EXISTS user_email_lower_unique ON auth_user(lower(email));",
            reverse_sql="DROP INDEX IF EXISTS user_email_lower_unique;",
        ),
    ]
