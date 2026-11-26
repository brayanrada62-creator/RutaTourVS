import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        ("usuarios", "0015_dispositivo"),
    ]

    operations = [
        migrations.CreateModel(
            name="CredencialBiometrica",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("credential_id", models.CharField(max_length=255, unique=True)),
                ("llave_publica", models.TextField()),
                ("contador", models.PositiveIntegerField(default=0)),
                ("creado", models.DateTimeField(auto_now_add=True)),
                (
                    "usuario",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="credenciales_biometricas",
                        to="usuarios.usuario",
                    ),
                ),
            ],
            options={
                "db_table": "credencial_biometrica",
            },
        ),
        migrations.CreateModel(
            name="RetoBiometrico",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("challenge", models.CharField(max_length=255, unique=True)),
                ("proposito", models.CharField(max_length=20)),
                ("expira", models.DateTimeField()),
                (
                    "usuario",
                    models.ForeignKey(
                        blank=True,
                        null=True,
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="retos_biometricos",
                        to="usuarios.usuario",
                    ),
                ),
            ],
            options={
                "db_table": "reto_biometrico",
            },
        ),
    ]
