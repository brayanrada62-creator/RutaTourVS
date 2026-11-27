from django.db import migrations, models


TIPOS = [
    ("COMPROBANTE_PLAN", "Comprobante de membresía pendiente"),
    ("PAGO_PENDIENTE", "Comprobante pendiente de revisión"),
    ("PAGO_APROBADO", "Pago aprobado"),
    ("CAMBIO_VIAJE", "Cambio en un viaje asignado"),
    ("NOVEDAD_INCIDENTE", "Novedad o incidente reportado"),
]


class Migration(migrations.Migration):
    dependencies = [("notificaciones", "0002_pago_pendiente")]

    operations = [
        migrations.AlterField("notificacion", "tipo", models.CharField(max_length=30, choices=TIPOS)),
        migrations.AlterField("preferencianotificacion", "tipo", models.CharField(max_length=30, choices=TIPOS)),
    ]
