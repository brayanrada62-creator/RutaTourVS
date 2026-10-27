from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("destinos", "0003_departamento_alter_destino_id_alter_hospedaje_id_and_more"),
        ("usuarios", "0008_fase7"),
    ]

    operations = [
        migrations.AddField(
            model_name="hospedaje",
            name="agencia",
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                to="usuarios.agencia",
            ),
        ),
        migrations.AddField(
            model_name="hospedaje",
            name="imagen",
            field=models.ImageField(blank=True, max_length=255, null=True, upload_to="hospedajes/"),
        ),
    ]
