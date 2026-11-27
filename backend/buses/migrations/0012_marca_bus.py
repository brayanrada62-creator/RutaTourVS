from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("buses", "0011_mapa_bus"),
    ]

    operations = [
        migrations.CreateModel(
            name="Marca",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("nombre", models.CharField(max_length=100, unique=True)),
            ],
            options={"db_table": "marca"},
        ),
        migrations.CreateModel(
            name="MarcaBus",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("marca", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="buses_de_marca", to="buses.marca")),
                ("bus", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="marcas_bus", to="buses.bus")),
            ],
            options={"db_table": "marcaBus"},
        ),
        migrations.AddConstraint(
            model_name="marcabus",
            constraint=models.UniqueConstraint(fields=("marca", "bus"), name="marca_bus_unico"),
        ),
    ]
