from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("buses", "0010_merge_0007_bus_tipo_bus_0009_bus_estado_choices"),
    ]

    operations = [
        migrations.CreateModel(
            name="MapaBus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("filas", models.PositiveIntegerField()),
                ("columnas", models.PositiveIntegerField()),
                ("pasillo_despues_de_columna", models.PositiveIntegerField()),
                ("bus", models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name="mapa", to="buses.bus")),
            ],
            options={"db_table": "mapas_bus"},
        ),
        migrations.CreateModel(
            name="AsientoBus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("numero", models.PositiveIntegerField()),
                ("fila", models.PositiveIntegerField()),
                ("columna", models.PositiveIntegerField()),
                ("lado", models.CharField(max_length=12)),
                ("bus", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="asientos_propios", to="buses.bus")),
            ],
            options={"db_table": "asientos_bus"},
        ),
        migrations.AddConstraint(
            model_name="asientobus",
            constraint=models.UniqueConstraint(fields=("bus", "numero"), name="asiento_bus_numero_unico"),
        ),
    ]
