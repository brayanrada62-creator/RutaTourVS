import django.db.models.deletion
from django.db import migrations, models


def quitar_agencia_superadmin(apps, schema_editor):
    Usuario = apps.get_model("usuarios", "Usuario")
    Rol = apps.get_model("usuarios", "Rol")
    roles_superadmin = []
    for rol in Rol.objects.all():
        nombre = (rol.rol or "").replace(" ", "").replace("_", "").lower()
        if nombre == "superadmin":
            roles_superadmin.append(rol.pk)
    if roles_superadmin:
        Usuario.objects.filter(rol_id__in=roles_superadmin).update(agencia=None)


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0003_alter_agencia_id_alter_rol_id_alter_usuario_id"),
    ]

    operations = [
        migrations.AlterField(
            model_name="usuario",
            name="agencia",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to="usuarios.agencia",
            ),
        ),
        migrations.RunPython(quitar_agencia_superadmin, migrations.RunPython.noop),
    ]
