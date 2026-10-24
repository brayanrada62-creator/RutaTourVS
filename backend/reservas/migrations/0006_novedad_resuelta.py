from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("reservas", "0005_fase7"),
    ]

    operations = [
        migrations.AddField(
            model_name="novedad",
            name="resuelta",
            field=models.BooleanField(default=False),
        ),
    ]
