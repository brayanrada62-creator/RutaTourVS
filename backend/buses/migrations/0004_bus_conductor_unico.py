from django.db import migrations, models


def quitar_duplicados(apps, schema_editor):
    """Deja una sola fila por cada par (bus, conductor): la de menor id.
    Las filas duplicadas son idénticas, así que no se pierde información."""
    BusConductor = apps.get_model("buses", "Bus_Conductor")
    vistos = set()
    for fila in BusConductor.objects.order_by("id"):
        par = (fila.bus_id, fila.conductor_id)
        if par in vistos:
            fila.delete()
        else:
            vistos.add(par)


class Migration(migrations.Migration):

    dependencies = [
        ("buses", "0003_remove_bus_conductor_alter_asiento_id_alter_bus_id_and_more"),
    ]

    operations = [
        migrations.RunPython(quitar_duplicados, migrations.RunPython.noop),
        migrations.AddConstraint(
            model_name="bus_conductor",
            constraint=models.UniqueConstraint(fields=("bus", "conductor"), name="bus_conductor_unico"),
        ),
    ]
