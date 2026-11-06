from django.db import migrations

BOGOTA = "Bogotá D.C."


def agregar_bogota(apps, schema_editor):
    """Bogotá no estaba en la lista inicial y ahora el destino exige un departamento existente."""
    Departamento = apps.get_model("destinos", "Departamento")
    if not Departamento.objects.filter(nombre=BOGOTA).exists():
        Departamento.objects.create(nombre=BOGOTA)


class Migration(migrations.Migration):

    dependencies = [
        ("destinos", "0006_normalizar_hospedajes"),
    ]

    operations = [
        # Al revertir no se borra: ya puede tener destinos asociados.
        migrations.RunPython(agregar_bogota, migrations.RunPython.noop),
    ]
