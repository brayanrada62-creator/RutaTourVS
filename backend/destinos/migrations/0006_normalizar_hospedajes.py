import django.db.models.deletion
from django.db import migrations, models


def copiar_destinos(apps, schema_editor):
    Hospedaje = apps.get_model("destinos", "Hospedaje")
    HospedajeDestino = apps.get_model("destinos", "HospedajeDestino")
    db_alias = schema_editor.connection.alias
    relaciones = (
        HospedajeDestino(hospedaje_id=hospedaje_id, destino_id=destino_id)
        for hospedaje_id, destino_id in Hospedaje.objects.using(db_alias).values_list("id", "destino_id")
    )
    HospedajeDestino.objects.using(db_alias).bulk_create(relaciones, batch_size=1000)


def restaurar_destino(apps, schema_editor):
    Hospedaje = apps.get_model("destinos", "Hospedaje")
    HospedajeDestino = apps.get_model("destinos", "HospedajeDestino")
    db_alias = schema_editor.connection.alias
    asignaciones = {}
    for hospedaje_id, destino_id in HospedajeDestino.objects.using(db_alias).values_list("hospedaje_id", "destino_id"):
        if hospedaje_id in asignaciones:
            raise RuntimeError("No se puede revertir una relación con varios destinos por hospedaje.")
        asignaciones[hospedaje_id] = destino_id

    hospedajes = Hospedaje.objects.using(db_alias).all()
    if hospedajes.exclude(id__in=asignaciones).exists():
        raise RuntimeError("No se puede revertir una relación de hospedaje sin destino.")
    for hospedaje_id, destino_id in asignaciones.items():
        Hospedaje.objects.using(db_alias).filter(id=hospedaje_id).update(destino_id=destino_id)


class Migration(migrations.Migration):

    dependencies = [
        ("destinos", "0005_merge_20261027_1329"),
    ]

    operations = [
        migrations.CreateModel(
            name="HospedajeDestino",
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
                    "destino",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="destinos.destino",
                    ),
                ),
                (
                    "hospedaje",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        to="destinos.hospedaje",
                    ),
                ),
            ],
            options={
                "db_table": "hospedaje_destino",
            },
        ),
        migrations.RunPython(copiar_destinos, restaurar_destino),
        migrations.RemoveField(
            model_name="hospedaje",
            name="destino",
        ),
        migrations.AddField(
            model_name="hospedaje",
            name="destinos",
            field=models.ManyToManyField(
                related_name="hospedajes",
                through="destinos.HospedajeDestino",
                to="destinos.destino",
            ),
        ),
        migrations.RemoveField(
            model_name="hospedaje",
            name="agencia",
        ),
        migrations.SeparateDatabaseAndState(
            database_operations=[],
            state_operations=[
                migrations.DeleteModel(
                    name="SitioTuristico",
                ),
            ],
        ),
        migrations.AddConstraint(
            model_name="hospedajedestino",
            constraint=models.UniqueConstraint(
                fields=("hospedaje", "destino"),
                name="hospedaje_destino_unico",
            ),
        ),
    ]
