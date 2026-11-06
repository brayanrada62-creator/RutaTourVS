from django.db import migrations, models


class Migration(migrations.Migration):
    """Amplía la descripción del destino y de su imagen a 2000 caracteres (solo agranda: no se pierde nada)."""

    dependencies = [
        ("destinos", "0007_departamento_bogota"),
    ]

    operations = [
        migrations.AlterField(
            model_name="destino",
            name="descripcion",
            field=models.CharField(max_length=2000),
        ),
        migrations.AlterField(
            model_name="imagendestino",
            name="descripcion",
            field=models.CharField(max_length=2000),
        ),
    ]
