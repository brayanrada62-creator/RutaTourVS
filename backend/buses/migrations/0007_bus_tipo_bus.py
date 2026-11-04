import django.db.models.deletion
from django.db import migrations, models


def copiar_tipo_bus(apps, schema_editor):
    Bus = apps.get_model("buses", "Bus")
    BusTipoBus = apps.get_model("buses", "BusTipoBus")
    db_alias = schema_editor.connection.alias
    relaciones = (
        BusTipoBus(bus_id=bus_id, tipo_bus_id=tipo_bus_id)
        for bus_id, tipo_bus_id in Bus.objects.using(db_alias).values_list("id", "tipo_bus_id")
    )
    BusTipoBus.objects.using(db_alias).bulk_create(relaciones, batch_size=1000)


def restaurar_tipo_bus(apps, schema_editor):
    Bus = apps.get_model("buses", "Bus")
    BusTipoBus = apps.get_model("buses", "BusTipoBus")
    db_alias = schema_editor.connection.alias
    asignaciones = {}
    for bus_id, tipo_bus_id in BusTipoBus.objects.using(db_alias).values_list("bus_id", "tipo_bus_id"):
        if bus_id in asignaciones:
            raise RuntimeError("No se puede revertir una relación con varios tipos de bus por bus.")
        asignaciones[bus_id] = tipo_bus_id

    buses = Bus.objects.using(db_alias).all()
    if buses.exclude(id__in=asignaciones).exists():
        raise RuntimeError("No se puede revertir una relación de bus sin tipo de bus.")
    for bus_id, tipo_bus_id in asignaciones.items():
        Bus.objects.using(db_alias).filter(id=bus_id).update(tipo_bus_id=tipo_bus_id)


class Migration(migrations.Migration):

    dependencies = [
        ("buses", "0006_fase7"),
    ]

    operations = [
        migrations.CreateModel(
            name="BusTipoBus",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                (
                    "bus",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="buses.bus",
                    ),
                ),
                (
                    "tipo_bus",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.PROTECT,
                        to="buses.tipobus",
                    ),
                ),
            ],
            options={
                "db_table": "bus_tipoBus",
            },
        ),
        migrations.RunPython(copiar_tipo_bus, restaurar_tipo_bus),
        migrations.RemoveField(
            model_name="bus",
            name="tipo_bus",
        ),
        migrations.AddField(
            model_name="bus",
            name="tipos_bus",
            field=models.ManyToManyField(
                related_name="buses",
                through="buses.BusTipoBus",
                to="buses.tipobus",
            ),
        ),
        migrations.AddConstraint(
            model_name="bustipobus",
            constraint=models.UniqueConstraint(
                fields=("bus", "tipo_bus"),
                name="bus_tipoBus_unico",
            ),
        ),
    ]
