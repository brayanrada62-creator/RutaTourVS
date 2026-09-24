from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('paquetes', '0002_alter_itinerario_id_alter_paquete_id_and_more'),
        ('buses', '0002_alter_asiento_id_alter_bus_id_alter_tipobus_id'),
        ('usuarios', '0002_alter_agencia_id_alter_rol_id_alter_usuario_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='paquete',
            name='precio',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.CreateModel(
            name='Viaje',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('fecha', models.DateField()),
                ('hora', models.TimeField()),
                ('precio', models.DecimalField(decimal_places=2, default=0, max_digits=12)),
                ('estado', models.CharField(default='PROGRAMADO', max_length=20)),
                ('bus', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='buses.bus')),
                ('conductor', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='usuarios.usuario')),
                ('paquete', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='paquetes.paquete')),
                ('tipo_bus', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, to='buses.tipobus')),
            ],
            options={
                'db_table': 'viajes',
            },
        ),
    ]
