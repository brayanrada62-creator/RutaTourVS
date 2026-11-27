from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("planes", "0003_remove_plan_precio_anual_remove_plan_precio_mensual_and_more")]

    operations = [
        migrations.AddField("solicitudplan", "periodo", models.CharField(
            max_length=20, default="mensual",
            choices=[("mensual", "Mensual"), ("trimestral", "Trimestral"), ("anual", "Anual")],
        )),
        migrations.AddField("solicitudplan", "precio", models.DecimalField(max_digits=12, decimal_places=2, default=0)),
        migrations.AddField("solicitudplan", "comprobante", models.ImageField(upload_to="comprobantes_planes/", blank=True)),
        migrations.AddField("solicitudplan", "motivo", models.CharField(max_length=255, blank=True)),
        migrations.AddField("solicitudplan", "inicia_el", models.DateField(null=True, blank=True)),
        migrations.AddField("solicitudplan", "vence_el", models.DateField(null=True, blank=True)),
    ]
