from django.contrib.auth.hashers import identify_hasher, make_password
from django.db import migrations


def cifrar(apps, schema_editor):
    """Convierte a hash las contraseñas guardadas en texto plano. La clave no cambia:
    el usuario sigue entrando con la misma, pero ya no queda legible en la base."""
    Usuario = apps.get_model("usuarios", "Usuario")
    for usuario in Usuario.objects.exclude(contrasena=""):
        try:
            identify_hasher(usuario.contrasena)
            continue  # ya está cifrada
        except ValueError:
            pass
        usuario.contrasena = make_password(usuario.contrasena)
        usuario.save(update_fields=["contrasena"])


class Migration(migrations.Migration):

    dependencies = [
        ("usuarios", "0006_merge_usuarioagencia_recuperarcontrasena"),
    ]

    operations = [
        migrations.RunPython(cifrar, migrations.RunPython.noop),
    ]
