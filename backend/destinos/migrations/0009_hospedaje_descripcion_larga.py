from django.db import migrations, models


class Migration(migrations.Migration):
    """Amplía la descripción del hospedaje a 2000 caracteres (solo agranda: no se pierde nada)."""

    dependencies = [
        ("destinos", "0008_descripcion_larga"),
    ]

    operations = [
        migrations.AlterField(
            model_name="hospedaje",
            name="descripcion",
            field=models.CharField(max_length=2000),
        ),
    ]
