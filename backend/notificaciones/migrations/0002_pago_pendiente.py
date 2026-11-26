from django.db import migrations, models


TIPOS = [
    ("PAGO_PENDIENTE", "Comprobante pendiente de revisión"),
    ("PAGO_APROBADO", "Pago aprobado"),
    ("CAMBIO_VIAJE", "Cambio en un viaje asignado"),
    ("NOVEDAD_INCIDENTE", "Novedad o incidente reportado"),
]


class Migration(migrations.Migration):
    dependencies = [("notificaciones", "0001_initial")]

    operations = [
        migrations.AlterField(
            model_name="notificacion", name="tipo",
            field=models.CharField(choices=TIPOS, max_length=30),
        ),
        migrations.AlterField(
            model_name="preferencianotificacion", name="tipo",
            field=models.CharField(choices=TIPOS, max_length=30),
        ),
    ]
