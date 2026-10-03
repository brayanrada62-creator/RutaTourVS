from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0004_superadmin_sin_agencia"),
    ]

    operations = [
        migrations.AddField(
            model_name="usuario",
            name="activo",
            field=models.BooleanField(default=True),
        ),
    ]
