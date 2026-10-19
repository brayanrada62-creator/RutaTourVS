from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('paquetes', '0005_alter_paquete_descripcion'),
    ]

    operations = [
        migrations.AddField(
            model_name='paquete',
            name='imagen',
            field=models.ImageField(blank=True, max_length=255, null=True, upload_to='paquetes/'),
        ),
    ]
